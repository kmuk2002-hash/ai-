from pydantic import BaseModel, Field

from agent import schemas
from agent.llm import get_llm
from agent.nodes.write_report import generate_report
from agent.prompts.common import quant_lines
from agent.prompts.verify import HUMAN, SYSTEM


class _VerifyResult(BaseModel):
    ok: bool = Field(description="리포트의 숫자가 모두 자료와 맞으면 true")
    problems: list[str] = Field(description="자료에 없거나 자료와 다른 숫자와 그 위치")


async def verify(state: schemas.MainState) -> dict:
    """[선택 노드, config.VERIFY_ENABLED] 리포트 숫자를 자료와 대조하고,
    문제가 있으면 그 내용을 알려 주고 한 번만 다시 쓰게 한다."""
    r: schemas.Report = state["report"]
    fs = state["fundamental_summary"]
    human = HUMAN.format(
        quant_lines=quant_lines(r.quant_snapshot),
        fundamental="\n".join([fs.business_overview, fs.stated_risks, fs.management_outlook, fs.recent_issues]),
        investment_thesis=r.investment_thesis, risks=r.risks,
        consensus_gap=r.consensus_gap, thesis_breakers=r.thesis_breakers,
    )
    result: _VerifyResult = await get_llm(temperature=0, tier="light").with_structured_output(_VerifyResult).ainvoke(
        [("system", SYSTEM), ("human", human)]
    )
    if result.ok or not result.problems:
        return {}
    fixed = await generate_report(state, feedback="\n".join(f"- {p}" for p in result.problems))
    return {"report": fixed}
