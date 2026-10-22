"""
W10 모델 라우팅 실험 — LangSmith Dataset + Experiment (W14)

질문: "관련성 검사(yes/no 분류)를 작은 모델에 맡겨도 판단이 틀리지 않으면서 빨라지나?"
     → 그렇다면 light 모델로 라우팅하는 근거, 아니라면 어디까지 작게 해도 되는지의 경계.

방법
  1) build : 종목마다 Tavily로 4개 주제(사업·리스크·전망·뉴스) 문서를 한 번 모은다.
             주제 조합을 바꿔 "정답이 정해진" 예제를 만든다.
               4개 주제 모두 / 3개 주제   → 정답 yes  (프롬프트 규칙: 넷 중 셋 이상이면 yes)
               2개 주제 / 1개 주제        → 정답 no
             → LangSmith Dataset으로 올린다. (LLM 호출 없음, Tavily만 사용)
  2) run   : 같은 Dataset을 모델마다 실제 relevance_check 프롬프트로 돌린다 = Experiment 1개.
             모델이 no라고 하면 실제 파이프라인처럼 query_rewrite도 이어서 부른다.
             채점(evaluator): 정답 일치, 구조화 출력 성공.
             요약(summary evaluator): 정확도, 거짓 yes 비율, 거짓 no 비율.
             LangSmith의 Datasets & Experiments 화면에서 모델별 실험을 나란히 비교할 수 있다.
  3) 터미널에 모델별 표를 출력하고 결과를 JSON으로 저장한다 (보고서용).

로컬 무료 모델(Ollama)로 돌린다. 비용이 들지 않으므로 '비용'은 호출당 지연시간과 토큰으로 본다.

    ollama serve
    ollama pull qwen3:8b && ollama pull qwen2.5:3b && ollama pull qwen2.5:0.5b
    cd backend
    python -m scripts.exp_model_routing ping                       # Ollama 연결·모델 확인 (몇 초)
    python -m scripts.exp_model_routing build --tickers AAPL NVDA MSFT
    python -m scripts.exp_model_routing run --models ollama:qwen3:8b ollama:qwen3.5:2b ollama:qwen2.5:0.5b --judge v1
    python -m scripts.exp_model_routing run --models ollama:qwen3:8b ollama:qwen3.5:2b ollama:qwen2.5:0.5b --judge v2

틀린 판단의 의미
  거짓 yes : 자료가 부족한데 충분하다고 판단 → 근거 부족한 요약·리포트 (품질 위험, 더 나쁨)
  거짓 no  : 충분한데 부족하다고 판단 → 쓸데없는 재검색 (지연·호출 낭비)
"""

import argparse
import asyncio
import itertools
import json
import statistics
import time
from datetime import date, datetime
from pathlib import Path

from langchain_core.documents import Document

from agent import config
from agent.llm import build_chat
from agent.prompts import fundamental as P
from agent.subgraphs.fundamental.nodes import _Coverage, _format_docs, _Relevance, decide_relevance

DATASET = "invest-relevance-routing"
OUT_DIR = config.CACHE_DIR / "experiments"
DOCS_FILE = OUT_DIR / "relevance_docs.json"
TOPICS = ["사업 구조와 경쟁 환경", "회사가 밝힌 리스크", "경영진 전망·가이던스", "최근 이슈"]


# ─────────────────────────────────────────────
# 1) Dataset 만들기
# ─────────────────────────────────────────────


async def _collect(ticker: str, as_of: date, per_topic: int) -> list[dict]:
    """주제별 검색어로 문서를 모으고, 각 문서에 어느 주제 검색어로 찾았는지(topic) 표시한다."""
    from agent.retrieval import web_search

    queries = [(q.format(ticker=ticker), days) for q, days in P.FIXED_QUERIES]
    docs = await web_search.search_fixed(queries, as_of)
    by_topic: dict[int, list[dict]] = {i: [] for i in range(len(TOPICS))}
    for d in docs:
        topic = next(i for i, (q, _) in enumerate(queries) if q == d.metadata.get("query"))
        if len(by_topic[topic]) < per_topic:
            by_topic[topic].append({"topic": topic, "title": d.metadata.get("title", ""),
                                    "url": d.metadata.get("url", ""), "content": d.page_content})
    return [d for i in range(len(TOPICS)) for d in by_topic[i]]


def _subsets() -> list[tuple[int, ...]]:
    """주제 조합: 4개 1 + 3개 4 + 2개 3 + 1개 1 = 9개 (yes 5 / no 4)"""
    return [
        (0, 1, 2, 3),
        *itertools.combinations(range(4), 3),
        (0, 3), (1, 2), (2, 3),
        (3,),
    ]


def make_examples(docs_by_ticker: dict[str, list[dict]]) -> list[dict]:
    examples = []
    for ticker, docs in docs_by_ticker.items():
        for subset in _subsets():
            picked = [d for d in docs if d["topic"] in subset]
            if not picked:
                continue
            text = _format_docs([
                Document(page_content=d["content"], metadata={"title": d["title"], "url": d["url"]})
                for d in picked
            ])
            examples.append({
                "inputs": {"ticker": ticker, "docs": text, "titles": [d["title"] for d in picked]},
                "outputs": {
                    "relevant": "yes" if len(subset) >= 3 else "no",
                    "topics": [TOPICS[i] for i in subset],
                    "missing": [t for i, t in enumerate(TOPICS) if i not in subset],
                },
                "metadata": {"ticker": ticker, "topic_count": len(subset)},
            })
    return examples


async def build(args) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs_by_ticker = {}
    for t in args.tickers:
        docs_by_ticker[t] = await _collect(t.upper(), args.date, args.per_topic)
        print(f"  {t}: 문서 {len(docs_by_ticker[t])}개 "
              f"(주제별 {[sum(d['topic'] == i for d in docs_by_ticker[t]) for i in range(4)]})")
    DOCS_FILE.write_text(json.dumps(docs_by_ticker, ensure_ascii=False, indent=1))

    examples = make_examples(docs_by_ticker)
    from langsmith import Client
    client = Client()
    if client.has_dataset(dataset_name=args.dataset):
        client.delete_dataset(dataset_name=args.dataset)   # 같은 이름이면 새로 만든다 (재현성)
    ds = client.create_dataset(
        dataset_name=args.dataset,
        description="relevance_check 정답셋: 주제 3개 이상이면 yes. scripts/exp_model_routing.py가 만든다.",
    )
    client.create_examples(dataset_id=ds.id, examples=examples)
    yes = sum(e["outputs"]["relevant"] == "yes" for e in examples)
    print(f"Dataset '{args.dataset}': 예제 {len(examples)}개 (yes {yes} / no {len(examples) - yes})")
    print(f"문서 원본 저장: {DOCS_FILE}")


# ─────────────────────────────────────────────
# 2) 모델별 Experiment
# ─────────────────────────────────────────────


def _tokens(msg) -> int | None:
    u = getattr(msg, "usage_metadata", None) or {}
    return u.get("total_tokens")


JUDGE_MAX_TOKENS = 400      # 판정 출력 상한 (주제 4개 × 문서 번호 목록이면 충분)
REWRITE_MAX_TOKENS = 60     # 검색어 한 줄
CALL_TIMEOUT_S = 60         # 한 번 호출이 이보다 길면 실패로 기록하고 다음 예제로


def make_target(spec: str, total: int, judge_mode: str = "v1"):
    llm = build_chat(spec, 0.0, JUDGE_MAX_TOKENS)
    rewriter = build_chat(spec, 0.0, REWRITE_MAX_TOKENS)
    schema = _Relevance if judge_mode == "v1" else _Coverage
    judge = llm.with_structured_output(schema, include_raw=True)
    system = P.RELEVANCE_SYSTEM if judge_mode == "v1" else P.COVERAGE_SYSTEM
    done = [0]

    async def target(inputs: dict) -> dict:
        """실제 relevance_check 노드와 같은 프롬프트. no면 query_rewrite까지 (실제 파이프라인 순서)."""
        t0 = time.perf_counter()
        timed_out = False
        try:
            out = await asyncio.wait_for(judge.ainvoke([
                ("system", system),
                ("human", P.RELEVANCE_HUMAN.format(ticker=inputs["ticker"], docs=inputs["docs"])),
            ]), CALL_TIMEOUT_S)
        except (asyncio.TimeoutError, Exception) as e:   # 시간 초과·형식 오류 = 판정 실패
            timed_out = isinstance(e, asyncio.TimeoutError)
            out = {"parsed": None, "raw": None}
        judge_s = time.perf_counter() - t0
        parsed = out.get("parsed")
        if judge_mode == "v2" and parsed is not None:
            # LLM은 주제별 근거 문서 번호만 고르고, 개수 세기·yes/no는 코드가 한다 (권위 게이트)
            parsed = decide_relevance(parsed, n_docs=len(inputs["titles"]))
        result = {
            "relevant": parsed.relevant if parsed else None,
            "missing": parsed.missing if parsed else None,
            "parse_ok": parsed is not None,
            "timeout": timed_out,
            "judge_latency_s": round(judge_s, 3),
            "judge_tokens": _tokens(out.get("raw")),
            "rewrite": None, "rewrite_latency_s": None, "rewrite_tokens": None,
        }
        if parsed and parsed.relevant == "no":
            t1 = time.perf_counter()
            msg = await rewriter.ainvoke([
                ("system", P.REWRITE_SYSTEM),
                ("human", P.REWRITE_HUMAN.format(
                    ticker=inputs["ticker"], question=parsed.missing or "부족한 주제",
                    titles="\n".join(f"- {t}" for t in inputs["titles"]),
                )),
            ])
            result.update(
                rewrite=(str(msg.content).strip().splitlines() or [""])[0].strip().strip('"'),
                rewrite_latency_s=round(time.perf_counter() - t1, 3),
                rewrite_tokens=_tokens(msg),
            )
        done[0] += 1
        print(f"  [{done[0]:>2}/{total}] {inputs['ticker']:<5} 판단={result['relevant'] or '형식실패'}"
              f"  {result['judge_latency_s']:.1f}s"
              + (f"  재작성: {result['rewrite']}" if result["rewrite"] else ""), flush=True)
        return result

    return target


# 예제 하나 채점 (LangSmith에 feedback으로 기록됨)
def correct(run, example) -> dict:
    ok = (run.outputs or {}).get("relevant") == example.outputs["relevant"]
    return {"key": "correct", "score": int(ok)}


def parse_ok(run, example) -> dict:
    return {"key": "parse_ok", "score": int(bool((run.outputs or {}).get("parse_ok")))}


# 실험 전체 요약 (LangSmith 실험 화면 상단에 표시됨)
def summary(runs, examples) -> dict:
    pairs = [((r.outputs or {}).get("relevant"), e.outputs["relevant"]) for r, e in zip(runs, examples)]
    n = len(pairs) or 1
    neg = sum(ref == "no" for _, ref in pairs) or 1
    pos = sum(ref == "yes" for _, ref in pairs) or 1
    return {"results": [
        {"key": "accuracy", "score": sum(p == ref for p, ref in pairs) / n},
        {"key": "false_yes_rate", "score": sum(p == "yes" and ref == "no" for p, ref in pairs) / neg},
        {"key": "false_no_rate", "score": sum(p == "no" and ref == "yes" for p, ref in pairs) / pos},
    ]}


def rewrite_valid(text: str | None, ticker: str) -> bool:
    """REWRITE_SYSTEM 규칙: 영어, 티커 포함, 10단어 이내 + 티커만 쓴 검색어는 무효(3단어 이상)"""
    if not text:
        return False
    ascii_ratio = sum(c.isascii() for c in text) / len(text)
    words = len(text.split())
    return ticker.upper() in text.upper() and 3 <= words <= 10 and ascii_ratio > 0.9


async def _warm_up(spec: str) -> None:
    """모델을 메모리에 올리는 첫 호출은 측정에서 뺀다."""
    await build_chat(spec, 0.0).ainvoke("ping")


async def ping(models: list[str]) -> None:
    import httpx

    try:
        tags = httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5).json()
    except Exception as e:
        raise SystemExit(f"Ollama 서버({config.OLLAMA_BASE_URL})에 연결할 수 없어요: {e}\n→ 다른 터미널에서 'ollama serve'")
    have = [m["name"] for m in tags.get("models", [])]
    print("설치된 모델:", ", ".join(have) or "(없음)")
    for spec in models:
        name = spec.partition(":")[2]
        if name not in have and f"{name}:latest" not in have:
            print(f"  ✗ {name}: 설치 안 됨 → ollama pull {name}")
            continue
        t0 = time.perf_counter()
        msg = await build_chat(spec, 0.0).ainvoke("Reply with one word: ok")
        t1 = time.perf_counter()
        await build_chat(spec, 0.0).ainvoke("Reply with one word: ok")
        print(f"  ✓ {name}: 첫 호출(적재 포함) {t1 - t0:.1f}s, 두 번째 {time.perf_counter() - t1:.1f}s → {str(msg.content)[:20]!r}")


async def run(args) -> None:
    from langsmith import aevaluate

    from langsmith import Client

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    examples = list(Client().list_examples(dataset_name=args.dataset, limit=args.limit))
    if not examples:
        raise SystemExit(f"Dataset '{args.dataset}'에 예제가 없어요. 먼저 build를 실행하세요.")
    print(f"Dataset '{args.dataset}': 예제 {len(examples)}개로 실험")
    table = []
    partial = OUT_DIR / f"routing_{args.judge}_{datetime.now():%Y%m%d_%H%M}.json"
    for spec in args.models:
        print(f"\n▶ {spec}  (모델 메모리 적재 중…)", flush=True)
        t0 = time.perf_counter()
        await _warm_up(spec)
        print(f"  적재 완료 {time.perf_counter() - t0:.1f}s", flush=True)
        results = await aevaluate(
            make_target(spec, len(examples), args.judge),
            data=examples,
            evaluators=[correct, parse_ok],
            summary_evaluators=[summary],
            experiment_prefix=f"routing-{args.judge}-{spec.replace(':', '-')}",
            metadata={"model": spec, "task": "relevance_check", "judge": args.judge, "wave": "W10"},
            max_concurrency=1,          # 지연시간을 공정하게 재려고 한 번에 하나씩
        )
        rows = []
        async for r in results:
            rows.append({"out": r["run"].outputs or {}, "ref": r["example"].outputs,
                         "ticker": r["example"].inputs["ticker"]})
        table.append(_summarize(f"{spec} [{args.judge}]", rows, getattr(results, "experiment_name", "")))
        partial.write_text(json.dumps(table, ensure_ascii=False, indent=1))   # 중간에 멈춰도 남게
        _print(table[-1:])

    _print(table)
    print(f"\n결과 저장: {partial}")
    print("LangSmith → Datasets & Experiments → "
          f"'{args.dataset}'에서 실험들을 선택해 Compare 하면 예제별 차이를 볼 수 있어요.")


def _summarize(spec: str, rows: list[dict], experiment: str) -> dict:
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.mean(xs), 3) if xs else None

    n = len(rows)
    pos = [r for r in rows if r["ref"]["relevant"] == "yes"]
    neg = [r for r in rows if r["ref"]["relevant"] == "no"]
    rewrites = [r for r in rows if r["out"].get("rewrite") is not None]
    return {
        "model": spec,
        "experiment": experiment,
        "n": n,
        "accuracy": round(sum(r["out"].get("relevant") == r["ref"]["relevant"] for r in rows) / max(n, 1), 3),
        "false_yes_rate": round(sum(r["out"].get("relevant") == "yes" for r in neg) / max(len(neg), 1), 3),
        "false_no_rate": round(sum(r["out"].get("relevant") == "no" for r in pos) / max(len(pos), 1), 3),
        "parse_fail": sum(not r["out"].get("parse_ok") for r in rows),
        "timeout": sum(bool(r["out"].get("timeout")) for r in rows),
        "judge_latency_s": mean([r["out"].get("judge_latency_s") for r in rows]),
        "judge_tokens": mean([r["out"].get("judge_tokens") for r in rows]),
        "rewrite_calls": len(rewrites),
        "rewrite_valid_rate": round(sum(rewrite_valid(r["out"]["rewrite"], r["ticker"]) for r in rewrites)
                                    / len(rewrites), 3) if rewrites else None,
        "rewrite_latency_s": mean([r["out"].get("rewrite_latency_s") for r in rewrites]),
    }


def _print(table: list[dict]) -> None:
    cols = [("model", "모델"), ("accuracy", "정확도"), ("false_yes_rate", "거짓yes"),
            ("false_no_rate", "거짓no"), ("parse_fail", "형식실패"), ("timeout", "시간초과"), ("judge_latency_s", "판단(s)"),
            ("judge_tokens", "판단토큰"), ("rewrite_calls", "재작성수"), ("rewrite_valid_rate", "재작성규칙"),
            ("rewrite_latency_s", "재작성(s)")]
    rows = [[h for _, h in cols]] + [["-" if t[k] is None else str(t[k]) for k, _ in cols] for t in table]
    widths = [max(len(r[i]) for r in rows) + 2 for i in range(len(cols))]
    print()
    for i, r in enumerate(rows):
        print("".join(c.ljust(w) for c, w in zip(r, widths)))
        if i == 0:
            print("-" * sum(widths))
    if len(table) > 1:
        base = table[0]
        print(f"\n기준(첫 모델) {base['model']} 대비")
        for t in table[1:]:
            if base["judge_latency_s"] and t["judge_latency_s"]:
                speed = (1 - t["judge_latency_s"] / base["judge_latency_s"]) * 100
                print(f"  {t['model']}: 판단 지연 {speed:+.0f}% 감소, 정확도 {t['accuracy'] - base['accuracy']:+.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Tavily로 문서를 모아 LangSmith Dataset 생성")
    b.add_argument("--tickers", nargs="+", default=["AAPL", "NVDA", "MSFT"])
    b.add_argument("--date", type=date.fromisoformat, default=date.today())
    b.add_argument("--per-topic", type=int, default=3, help="주제당 문서 수 (프롬프트 길이 조절)")
    b.add_argument("--dataset", default=DATASET)
    r = sub.add_parser("run", help="모델별 Experiment 실행 (첫 모델이 비교 기준)")
    r.add_argument("--models", nargs="+",
                   default=[f"ollama:{config.OLLAMA_MODEL}", f"ollama:{config.OLLAMA_MODEL_LIGHT}"])
    r.add_argument("--dataset", default=DATASET)
    r.add_argument("--limit", type=int, help="예제 일부만 (빠른 확인용, 예: 6)")
    r.add_argument("--judge", choices=["v1", "v2"], default="v1",
                   help="v1: LLM이 yes/no를 직접 / v2: LLM은 주제별 근거 문서만, yes/no는 코드가")
    pg = sub.add_parser("ping", help="Ollama 연결과 모델별 응답 속도 확인 (LangSmith 안 씀)")
    pg.add_argument("--models", nargs="+",
                    default=[f"ollama:{config.OLLAMA_MODEL}", f"ollama:{config.OLLAMA_MODEL_LIGHT}"])
    args = ap.parse_args()
    if args.cmd == "ping":
        asyncio.run(ping(args.models))
        return
    if not config.TRACING_ENABLED:
        raise SystemExit("LangSmith 키·LANGSMITH_TRACING=true가 필요합니다 (.env).")
    asyncio.run(build(args) if args.cmd == "build" else run(args))


if __name__ == "__main__":
    main()
