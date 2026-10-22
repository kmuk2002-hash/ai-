"""
파이프라인 단위 Before/After 실험 — 같은 입력을 설정만 바꿔 여러 번 돌리고 LangSmith 기록으로 비교한다.

    cd backend
    # W10 모델 라우팅: 전부 heavy vs 분류만 light (로컬 무료 모델)
    python -m scripts.exp_pipeline AAPL --provider ollama --variant llm=single --variant llm=tiered --repeat 3

    # W08 검증 노드 끄기/켜기
    python -m scripts.exp_pipeline AAPL --provider ollama --variant verify=off --variant verify=on --repeat 2

    # W04 웹 검색 방식
    python -m scripts.exp_pipeline AAPL --provider ollama --variant web=fixed --variant web=agent --repeat 3

설정 키: llm=single|tiered, web=fixed|agent, verify=on|off (쉼표로 묶기: --variant llm=tiered,verify=on)

동작
  - 실행마다 exp:<실험ID>와 variant:<설정> 태그를 붙인다 → 이전 실행과 섞이지 않는다.
  - 변형을 번갈아(A B A B …) 실행해 시간대·캐시 상태 차이가 한쪽에 몰리지 않게 한다.
  - 첫 실행 전에 한 번 '예열' 실행을 하고 비교에서 뺀다 (Alpha Vantage 캐시, Ollama 모델 로딩).
  - 끝나면 scripts.langsmith_stats로 변형별 평균(전체·노드별 지연, 토큰, 비용)을 출력한다.
"""

import argparse
import asyncio
import time
import uuid
from datetime import date

from agent import config

KEYS = {"llm": ("LLM_ROUTING", {"single", "tiered"}),
        "web": ("WEB_SEARCH_MODE", {"fixed", "agent"}),
        "verify": (None, {"on", "off"})}


def parse_variant(text: str) -> dict[str, str]:
    out = {}
    for part in text.split(","):
        k, _, v = part.partition("=")
        if k not in KEYS or v not in KEYS[k][1]:
            raise SystemExit(f"잘못된 설정: {part} (가능: {', '.join(f'{k}={sorted(v[1])}' for k, v in KEYS.items())})")
        out[k] = v
    return out


async def run_once(ticker: str, as_of: date, settings: dict[str, str], tags: list[str]) -> float:
    from agent.graph import build_graph
    from agent.runner import analyze

    base = {"LLM_ROUTING": config.LLM_ROUTING, "WEB_SEARCH_MODE": config.WEB_SEARCH_MODE}
    for k, v in settings.items():
        if KEYS[k][0]:
            setattr(config, KEYS[k][0], v)
    config.RUN_TAGS = tags
    t0 = time.perf_counter()
    try:
        graph = build_graph(verify_enabled=settings.get("verify") == "on")
        await analyze(ticker, "US", as_of, graph=graph, source="exp")
    finally:
        for attr, v in base.items():          # 다음 변형에 영향이 없도록 되돌린다
            setattr(config, attr, v)
        config.RUN_TAGS = []
    return time.perf_counter() - t0


async def main_async(args) -> None:
    variants = [(v, parse_variant(v)) for v in args.variant]
    exp_id = uuid.uuid4().hex[:6]
    exp_tag = f"exp:{exp_id}"
    print(f"실험 {exp_tag} · {args.ticker} · provider={config.LLM_PROVIDER} · 변형 {len(variants)}개 × {args.repeat}회")

    if not args.no_warmup:
        print("  예열 실행 (비교에서 제외)…")
        await run_once(args.ticker, args.date, variants[0][1], ["warmup"])

    for i in range(args.repeat):
        for name, settings in variants:
            sec = await run_once(args.ticker, args.date, settings, [exp_tag, f"variant:{name}"])
            print(f"  [{i + 1}/{args.repeat}] {name:<20} {sec:6.1f}s")

    # LangSmith로 추적 전송이 끝나고 집계(토큰·비용 합계)가 반영될 때까지 기다린다
    from langchain_core.tracers.langchain import wait_for_all_tracers
    wait_for_all_tracers()
    print(f"\nLangSmith 집계 대기 {args.wait}초…")
    time.sleep(args.wait)

    from scripts import langsmith_stats
    langsmith_stats.main(["--tag", exp_tag, "--limit", str(args.repeat * 2 + 5),
                          "--compare", *[f"variant:{n}" for n, _ in variants]])
    print(f"\n다시 보기: python -m scripts.langsmith_stats --tag {exp_tag} "
          f"--compare {' '.join(f'variant:{n}' for n, _ in variants)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker")
    ap.add_argument("--variant", action="append", required=True, help="예) llm=single  (2개 이상)")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--provider", choices=["openai", "ollama"], help="기본: .env의 LLM_PROVIDER")
    ap.add_argument("--wait", type=int, default=15)
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()
    if len(args.variant) < 2:
        raise SystemExit("--variant를 2개 이상 주세요.")
    if args.provider:
        config.LLM_PROVIDER = args.provider
    if not config.TRACING_ENABLED:
        raise SystemExit("LangSmith 키·LANGSMITH_TRACING=true가 필요합니다 (.env).")
    args.ticker = args.ticker.upper()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
