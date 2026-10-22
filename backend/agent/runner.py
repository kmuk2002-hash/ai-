"""
분석 1회를 실행하는 입구. FastAPI(/analyze, /analyze/stream), 노트북, CLI가 모두 이 모듈을 쓴다.
→ 어디서 실행하든 LangSmith에 같은 이름·태그·메타데이터로 기록된다.

    analyze()        : 끝까지 실행하고 최종 State를 돌려준다
    analyze_stream() : 노드가 끝날 때마다 진행 이벤트를 내보내고, 마지막에 최종 State를 준다 (SSE용)

노트북:
    from agent.runner import analyze
    result = await analyze("AAPL")              # result["report"]
"""

from datetime import date
from typing import Any, AsyncIterator

from agent import config
from agent.tracing import run_config


async def _has_past(ticker: str, market: str) -> bool | None:
    """태그용 사전 확인. DB가 없으면 None(태그 생략)."""
    if not config.DATABASE_URL:
        return None
    try:
        from storage.repositories.decision_repo import list_decisions
        return bool(await list_decisions(ticker, market))
    except Exception:
        return None


def _av_cache_warm(ticker: str, market: str) -> bool | None:
    """오늘 Alpha Vantage 캐시가 다 있으면 warm (API 호출 없이 끝남)."""
    if market != "US":
        return None
    from agent.adapters import cache
    from agent.adapters.us_alphavantage import FUNCTIONS, SOURCE, _api_message
    for fn, _ in FUNCTIONS:
        data = cache.load(SOURCE, fn, ticker.upper())
        if data is None or _api_message(data):
            return False
    return True


async def _prepare(ticker: str, market: str, as_of_date: date | None, graph, source: str):
    """그래프 · 입력 · 실행 설정(LangSmith 태그)을 만든다."""
    if graph is None:
        from agent.graph import build_graph
        graph = build_graph()
    ticker, as_of_date = ticker.upper(), as_of_date or date.today()
    cfg = run_config(
        ticker, market, as_of_date,
        has_past=await _has_past(ticker, market),
        cache_warm=_av_cache_warm(ticker, market),
        source=source,
        verify_enabled="verify" in graph.get_graph().nodes,
    )
    inp = {"ticker": ticker, "market": market, "as_of_date": as_of_date}
    return graph, inp, cfg


async def analyze(
    ticker: str,
    market: str = "US",
    as_of_date: date | None = None,
    *,
    graph=None,
    source: str = "notebook",
) -> dict:
    """그래프를 실행하고 최종 State(dict)를 돌려준다. graph를 안 주면 새로 컴파일한다."""
    graph, inp, cfg = await _prepare(ticker, market, as_of_date, graph, source)
    return await graph.ainvoke(inp, config=cfg)


async def analyze_stream(
    ticker: str,
    market: str = "US",
    as_of_date: date | None = None,
    *,
    graph=None,
    source: str = "api",
) -> AsyncIterator[dict[str, Any]]:
    """진행 이벤트를 차례로 내보낸다.

    {"type": "node", "node": "quant"}                                 메인 그래프 노드 하나가 끝남
    {"type": "node", "node": "past_decision", "has_past": True}      과거 결정 유무를 함께 알려 준다
    {"type": "step", "node": "fundamental", "step": "relevance_check"} 서브그래프 안 단계가 끝남
    {"type": "done", "state": {...}}                                  마지막: 최종 State
    """
    graph, inp, cfg = await _prepare(ticker, market, as_of_date, graph, source)
    final: dict = {}

    # stream_mode 두 개 + subgraphs=True → (namespace, mode, data)
    #   namespace가 ()면 메인 그래프, ("fundamental:<id>",)면 서브그래프
    #   "updates": 끝난 노드 이름 → 진행 표시용 / "values": 매 단계의 전체 State → 마지막 것이 최종 결과
    async for ns, mode, data in graph.astream(
        inp, config=cfg, stream_mode=["updates", "values"], subgraphs=True
    ):
        if mode == "values":
            if not ns:
                final = data
            continue
        for node, update in data.items():
            if ns:
                yield {"type": "step", "node": ns[0].split(":")[0], "step": node}
            else:
                event: dict[str, Any] = {"type": "node", "node": node}
                if node == "past_decision":
                    event["has_past"] = bool(update and update.get("past_decision") is not None)
                yield event

    yield {"type": "done", "state": final}
