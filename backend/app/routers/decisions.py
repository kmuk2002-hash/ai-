import psycopg
from fastapi import APIRouter, HTTPException

from agent.schemas import Market
from app.dto import DecisionCreate
from storage.repositories import decision_repo, report_repo

router = APIRouter()


@router.post("/decisions")
async def create_decision(body: DecisionCreate):
    if await report_repo.get_report(body.report_id) is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다.")
    try:
        return await decision_repo.create_decision(**body.model_dump())
    except psycopg.errors.RaiseException as e:   # DB 트리거: 다른 리포트의 하이라이트를 근거로 연결
        raise HTTPException(400, str(e).splitlines()[0]) from e


@router.get("/decisions")
async def list_all_decisions():
    """전체 결정, 최신순 (기록 보관함 화면용)"""
    return await decision_repo.list_all_decisions()


@router.get("/decisions/{ticker}")
async def list_decisions(ticker: str, market: Market | None = None):
    return await decision_repo.list_decisions(ticker, market)
