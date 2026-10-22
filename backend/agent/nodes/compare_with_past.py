from typing import Literal

from pydantic import BaseModel, Field

from agent import schemas
from agent.llm import get_llm
from agent.prompts.common import quant_lines
from agent.prompts.compare_with_past import HUMAN, SYSTEM

_TAG_LABEL = {"support": "근거", "concern": "우려", "to_verify": "확인 필요", "disagree": "반대"}
_ACTION_LABEL = {"buy": "매수", "hold": "보류", "sell": "매도"}


class _Check(BaseModel):
    category: Literal["data_change", "thesis_breaker", "to_verify", "thesis_validity"]
    target: str = Field(description="점검 대상 (조건 문장, 하이라이트 원문, 지표 이름)")
    status: Literal["triggered", "not_triggered", "insufficient_evidence"]
    evidence: str = Field(description="판단 근거 1~2문장")


class _ReviewBody(BaseModel):
    """LLM이 채우는 부분. 출처는 붙이지 않는다(지어낼 수 있어서)."""

    summary: str = Field(description="과거 결정 대비 달라진 점 요약 3~5문장")
    checks: list[_Check]


def _highlights_text(groups: list[schemas.HighlightGroup]) -> str:
    if not groups:
        return "(없음)"
    lines = []
    for g in groups:
        quoted = " / ".join(s.quoted_text for s in g.spans)
        memo = f" (메모: {g.comment})" if g.comment else ""
        lines.append(f"- [{_TAG_LABEL.get(g.tag, g.tag)}] {quoted}{memo}")
    return "\n".join(lines)


async def compare_with_past(state: schemas.MainState) -> dict:
    """새 리포트 vs 과거 결정 비교 → 기존 report에 past_decision_review만 채운다.
    리포트의 다른 필드는 건드리지 않는다(과거에 끌려가지 않은 독립 분석을 유지)."""
    past: schemas.PastDecision = state["past_decision"]
    report: schemas.Report = state["report"]
    d = past.decision

    human = HUMAN.format(
        ticker=state["ticker"], market=state["market"],
        decided_at=d.decided_at.date().isoformat(),
        action=_ACTION_LABEL.get(d.action, d.action), confidence=d.confidence,
        weight="미정" if d.weight is None else f"{d.weight * 100:.1f}%",
        my_thesis=d.my_thesis, my_thesis_breaker=d.my_thesis_breaker,
        past_as_of=past.report.as_of_date, past_thesis=past.report.investment_thesis,
        past_breakers=past.report.thesis_breakers,
        past_quant=quant_lines(past.report.quant_snapshot),
        highlights=_highlights_text(past.highlights),
        as_of_date=state["as_of_date"], thesis=report.investment_thesis, risks=report.risks,
        consensus_gap=report.consensus_gap, quant=quant_lines(report.quant_snapshot),
    )
    llm = get_llm().with_structured_output(_ReviewBody)
    body: _ReviewBody = await llm.ainvoke([("system", SYSTEM), ("human", human)])

    review = schemas.PastDecisionReview(
        summary=body.summary,
        checks=[schemas.PastDecisionCheck(**c.model_dump()) for c in body.checks],
    )
    return {"report": report.model_copy(update={"past_decision_review": review})}
