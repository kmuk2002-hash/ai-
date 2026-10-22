import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from agent.runner import analyze as run_analysis
from agent.runner import analyze_stream as run_analysis_stream
from app.dto import AnalyzeRequest
from storage.repositories import report_repo

router = APIRouter()
log = logging.getLogger(__name__)


def _check_market(req: AnalyzeRequest) -> None:
    if req.market != "US":
        raise HTTPException(400, "국내(KR) 시장은 아직 지원하지 않습니다.")


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, request: Request):
    """그래프 실행 → 리포트 저장(이후 수정 불가) → {id, ...report} 반환"""
    _check_market(req)
    graph = request.app.state.agent
    try:
        # 태그·메타데이터를 붙여 실행 → LangSmith에서 종목·방식별로 필터 가능
        result = await run_analysis(req.ticker, req.market, req.as_of_date, graph=graph, source="api")
    except Exception as e:
        log.exception("분석 실패")
        # Alpha Vantage 한도 초과, API 키 오류 등 원인이 화면에 보이도록 메시지를 그대로 전달
        raise HTTPException(502, f"분석 중 오류: {e}") from e

    return await report_repo.save_report(result["report"])


def _sse(event: str, data) -> str:
    """Server-Sent Events 한 건: 'event: 이름\\ndata: JSON\\n\\n'"""
    return f"event: {event}\ndata: {json.dumps(jsonable_encoder(data), ensure_ascii=False)}\n\n"


@router.post("/analyze/stream")
async def analyze_stream(req: AnalyzeRequest, request: Request):
    """/analyze와 같은 일을 하되, 노드가 끝날 때마다 진행 상황을 SSE로 보낸다.

    event: node    {"node": "quant", "elapsed": 2.8}
    event: step    {"node": "fundamental", "step": "relevance_check", "elapsed": 9.1}
    event: report  {id, ...report}      ← 저장된 리포트 (/analyze 응답과 같은 형태)
    event: error   {"detail": "..."}
    """
    _check_market(req)
    graph = request.app.state.agent

    async def events():
        started = time.monotonic()
        try:
            async for ev in run_analysis_stream(
                req.ticker, req.market, req.as_of_date, graph=graph, source="api"
            ):
                if ev["type"] == "done":
                    saved = await report_repo.save_report(ev["state"]["report"])
                    yield _sse("report", saved)
                else:
                    ev["elapsed"] = round(time.monotonic() - started, 1)
                    yield _sse(ev.pop("type"), ev)
        except Exception as e:
            log.exception("분석 실패")
            yield _sse("error", {"detail": f"분석 중 오류: {e}"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
