"""
LangSmith에 기록된 최근 분석 실행을 표로 정리한다. 보고서의 Before/After 숫자용.

    cd backend
    python -m scripts.langsmith_stats                       # 최근 20개
    python -m scripts.langsmith_stats --tag web:agent       # 태그로 필터
    python -m scripts.langsmith_stats --ticker AAPL
    python -m scripts.langsmith_stats --compare web:fixed web:agent      # 그룹별 평균 비교
    python -m scripts.langsmith_stats --compare av_cache:cold av_cache:warm
    python -m scripts.langsmith_stats --compare verify:off verify:on
    python -m scripts.langsmith_stats --compare llm:single llm:tiered

태그는 agent/tracing.py의 run_config()가 붙인다:
  market:US, web:fixed|agent, verify:on|off, has_past|no_past, av_cache:warm|cold, source:api|cli|notebook, llm:tiered|single
"""

import argparse
import statistics
from collections import defaultdict
from typing import Any, Iterable

from agent import config


def _latency(run: Any) -> float | None:
    if run.start_time and run.end_time:
        return (run.end_time - run.start_time).total_seconds()
    return None


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def build_filter(tags: list[str], ticker: str | None) -> str | None:
    parts = [f'has(tags, "{t}")' for t in tags]
    if ticker:
        parts.append(f'and(eq(metadata_key, "ticker"), eq(metadata_value, "{ticker.upper()}"))')
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else "and(" + ", ".join(parts) + ")"


def collect(client: Any, project: str, *, limit: int, tags: list[str], ticker: str | None) -> list[dict]:
    """루트 실행(분석 1회) 목록 + 각 실행의 노드별 지연 시간"""
    roots = list(client.list_runs(
        project_name=project, is_root=True, limit=limit, filter=build_filter(tags, ticker),
    ))
    rows = []
    for r in roots:
        children = client.list_runs(project_name=project, trace_id=r.trace_id)
        nodes: dict[str, float] = {}
        for c in children:
            if c.parent_run_id == r.id:            # 그래프 바로 아래 = LangGraph 노드
                lat = _latency(c)
                if lat is not None:
                    nodes[c.name] = nodes.get(c.name, 0.0) + lat
        rows.append({
            "name": r.name,
            "tags": [t for t in (r.tags or []) if ":" in t or t in ("has_past", "no_past")],
            "latency": _latency(r),
            "nodes": nodes,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "total_cost": _num(getattr(r, "total_cost", None)),
            "error": r.error,
        })
    return rows


def _fmt(v: Any, nd: int = 1) -> str:
    if v is None:
        return "-"
    return f"{v:,.{nd}f}" if isinstance(v, float) else f"{v:,}"


def print_runs(rows: list[dict]) -> None:
    if not rows:
        print("실행 기록이 없습니다.")
        return
    node_names = sorted({n for r in rows for n in r["nodes"]})
    header = ["run", "tags", "total(s)", *[f"{n}(s)" for n in node_names], "prompt_tok", "compl_tok", "cost($)"]
    table = [header]
    for r in rows:
        table.append([
            r["name"] + (" ⚠" if r["error"] else ""), " ".join(r["tags"]), _fmt(r["latency"]),
            *[_fmt(r["nodes"].get(n)) for n in node_names],
            _fmt(r["prompt_tokens"]), _fmt(r["completion_tokens"]), _fmt(r["total_cost"], 4),
        ])
    widths = [max(len(str(row[i])) for row in table) for i in range(len(header))]
    for i, row in enumerate(table):
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths)))
        if i == 0:
            print("  ".join("-" * w for w in widths))


def summarize(rows: Iterable[dict]) -> dict:
    rows = [r for r in rows if not r["error"]]
    def avg(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return statistics.mean(vals) if vals else None
    node_avg = defaultdict(list)
    for r in rows:
        for n, v in r["nodes"].items():
            node_avg[n].append(v)
    return {
        "runs": len(rows),
        "latency": avg("latency"),
        "total_tokens": avg("total_tokens"),
        "total_cost": avg("total_cost"),
        "nodes": {n: statistics.mean(v) for n, v in node_avg.items()},
    }


def print_compare(groups: dict[str, dict]) -> None:
    node_names = sorted({n for g in groups.values() for n in g["nodes"]})
    header = ["group", "runs", "avg total(s)", *[f"avg {n}(s)" for n in node_names], "avg tokens", "avg cost($)"]
    table = [header] + [
        [name, str(g["runs"]), _fmt(g["latency"]), *[_fmt(g["nodes"].get(n)) for n in node_names],
         _fmt(g["total_tokens"], 0), _fmt(g["total_cost"], 4)]
        for name, g in groups.items()
    ]
    widths = [max(len(str(row[i])) for row in table) for i in range(len(header))]
    for i, row in enumerate(table):
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths)))
        if i == 0:
            print("  ".join("-" * w for w in widths))


def main(argv: list[str] | None = None, client: Any = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=config.LANGSMITH_PROJECT)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--tag", action="append", default=[], help="태그 필터 (여러 번 가능)")
    ap.add_argument("--ticker")
    ap.add_argument("--compare", nargs="+", metavar="TAG", help="태그별 평균 비교")
    args = ap.parse_args(argv)

    if client is None:
        if not config.LANGSMITH_API_KEY:
            raise SystemExit("LANGSMITH_API_KEY가 없습니다. .env에 키를 넣어 주세요.")
        from langsmith import Client
        client = Client(api_url=config.LANGSMITH_ENDPOINT) if config.LANGSMITH_ENDPOINT else Client()

    if args.compare:
        groups = {
            tag: summarize(collect(client, args.project, limit=args.limit, tags=[*args.tag, tag], ticker=args.ticker))
            for tag in args.compare
        }
        print_compare(groups)
    else:
        print_runs(collect(client, args.project, limit=args.limit, tags=args.tag, ticker=args.ticker))


if __name__ == "__main__":
    main()
