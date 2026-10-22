"""
API 요청 본문 모델. 응답은 저장된 행(dict)을 그대로 돌려준다(frontend/README.md의 계약).
"""

from datetime import date

from pydantic import BaseModel, Field

from agent.schemas import DecisionAction, HighlightSpan, HighlightTag, Market


class AnalyzeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=12)
    market: Market
    as_of_date: date


class HighlightCreate(BaseModel):
    tag: HighlightTag
    comment: str | None = None
    spans: list[HighlightSpan] = Field(min_length=1)


class DecisionCreate(BaseModel):
    report_id: str
    ticker: str
    market: Market
    action: DecisionAction
    weight: float | None = Field(default=None, ge=0, le=1)
    confidence: int = Field(ge=1, le=5)
    my_thesis: str
    my_thesis_breaker: str
    evidence_group_ids: list[str] = []
