"""
터미널에서 분석 1회 실행 (FastAPI 없이). LangSmith에는 source:cli 태그로 기록된다.

    cd backend
    python -m scripts.run_analysis AAPL
    python -m scripts.run_analysis AAPL --date 2026-10-21 --web agent --verify
    python -m scripts.run_analysis AAPL --llm single      # 모든 노드를 heavy 모델로 (라우팅 Before)
    python -m scripts.run_analysis AAPL --provider ollama --llm tiered   # 로컬 무료 모델로
"""

import argparse
import asyncio
from datetime import date

from agent import config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--market", default="US")
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--web", choices=["fixed", "agent"], help="웹 검색 방식 (기본: .env의 WEB_SEARCH_MODE)")
    ap.add_argument("--verify", action="store_true", help="검증 노드 켜기")
    ap.add_argument("--llm", choices=["tiered", "single"], help="모델 라우팅 (기본: .env의 LLM_ROUTING)")
    ap.add_argument("--provider", choices=["openai", "ollama"], help="LLM 제공자 (기본: .env의 LLM_PROVIDER)")
    args = ap.parse_args()

    if args.web:
        config.WEB_SEARCH_MODE = args.web
    if args.llm:
        config.LLM_ROUTING = args.llm
    if args.provider:
        config.LLM_PROVIDER = args.provider
    from agent.graph import build_graph
    from agent.runner import analyze

    graph = build_graph(verify_enabled=args.verify or None)
    result = asyncio.run(analyze(args.ticker, args.market, args.date, graph=graph, source="cli"))

    r = result["report"]
    for field in ("investment_thesis", "risks", "consensus_gap", "thesis_breakers"):
        print(f"\n[{field}]\n{getattr(r, field)}")
    if r.past_decision_review:
        print(f"\n[past_decision_review]\n{r.past_decision_review.summary}")
    print("\n출처:", *[f"- {s.title} ({s.url})" for s in r.sources], sep="\n")
    print(f"\nLangSmith 추적: {'켜짐 → 프로젝트 ' + config.LANGSMITH_PROJECT if config.TRACING_ENABLED else '꺼짐'}")


if __name__ == "__main__":
    main()
