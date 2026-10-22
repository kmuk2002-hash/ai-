from pydantic import BaseModel, Field

from agent.prompts.common import quant_lines
from agent import schemas
from agent.llm import get_llm
from agent.prompts.write_report import HUMAN, SYSTEM

class _ReportBody(BaseModel):
    """LLM이 채우는 부분. 출처(sources)는 LLM이 지어낼 수 있어서 코드에서 넣는다."""
    investment_thesis: str = Field(description="투자 논리: 이 종목을 보유할 이유")
    risks: str = Field(description="주요 리스크")
    consensus_gap: str = Field(description="시장 기대치와 실제 데이터가 갈리는 지점")
    thesis_breakers: str = Field(description="투자 논리가 틀렸다고 판단할, 숫자로 확인 가능한 조건들")

def _sources(state: schemas.MainState) -> list[schemas.Source]:
    sources = list(state["fundamental_summary"].sources)
    sources.append(
        schemas.Source(
            title="Alpha Vantage (EARNINGS, TIME_SERIES_DAILY, TIME_SERIES_WEEKLY)",
            url="https://www.alphavantage.co",
            doc_type="quant_api",
        )
    )
    return sources

async def generate_report(state: schemas.MainState, feedback: str | None = None) -> schemas.Report:
    """리포트 본문을 LLM으로 만든다. feedback이 있으면(검증 노드가 찾은 문제) 고쳐서 다시 쓴다."""
    fs = state["fundamental_summary"]
    qs = state["quant_snapshot"]

    human = HUMAN.format(
        ticker=state["ticker"],
        market=state["market"],
        as_of_date=state["as_of_date"],
        business_overview=fs.business_overview,
        stated_risks=fs.stated_risks,
        management_outlook=fs.management_outlook,
        recent_issues=fs.recent_issues,
        quant_lines=quant_lines(qs),
        quant_summary=state.get("quant_summary") or "없음",
    )
    if feedback:
        human += f"\n\n[이전 초안에서 발견된 문제 - 반드시 고쳐서 다시 쓰세요]\n{feedback}"

    llm = get_llm().with_structured_output(_ReportBody)
    body: _ReportBody = await llm.ainvoke([("system", SYSTEM), ("human", human)])

    return schemas.Report(
        **body.model_dump(),
        sources=_sources(state),
        ticker=state["ticker"],
        market=state["market"],
        as_of_date=state["as_of_date"],
        quant_snapshot=qs,
    )


async def write_report(state: schemas.MainState) -> dict:
    """fundamental + quant 결과로 리포트 작성. 과거 결정은 보지 않음"""
    return {"report": await generate_report(state)}
