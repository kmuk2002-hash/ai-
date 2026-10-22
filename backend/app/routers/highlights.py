from fastapi import APIRouter, HTTPException

from app.dto import HighlightCreate
from storage.repositories import highlight_repo, report_repo

router = APIRouter()


@router.get("/reports/{report_id}/highlights")
async def list_highlights(report_id: str):
    return await highlight_repo.list_groups(report_id)


@router.post("/reports/{report_id}/highlights")
async def create_highlight(report_id: str, body: HighlightCreate):
    if await report_repo.get_report(report_id) is None:
        raise HTTPException(404, "리포트를 찾을 수 없습니다.")
    return await highlight_repo.create_group(report_id, body.tag, body.comment, body.spans)
