from fastapi import APIRouter, HTTPException

from agent.schemas import Market
from storage.repositories import report_repo

router = APIRouter()


@router.get("/reports")
async def list_reports(ticker: str | None = None, market: Market | None = None):
    return await report_repo.list_reports(ticker, market)


@router.get("/notifications")
async def list_notifications():
    """결정 이후 소식: 결정한 종목을 다시 분석했을 때의 '과거 결정 대비' 점검 결과"""
    return await report_repo.list_notifications()


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    row = await report_repo.get_report(report_id)
    if row is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다.")
    return row
