from agent import schemas
from agent.adapters.base import fetch_quant_snapshot
from agent.llm import get_llm
from agent.prompts.common import quant_lines
from agent.prompts.quant import HUMAN,SYSTEM

async def _interpret(state: schemas.MainState, snapshot: schemas.QuantSnapshot) ->str:
    messages = [
        ("system",SYSTEM),
        ("human",HUMAN.format(
            ticker=state["ticker"],
            market=state["market"],
            as_of_date=state["as_of_date"],
            quant_lines=quant_lines(snapshot),
        ))
    ]
    response = await get_llm().ainvoke(messages)
    return response.content

async def quant(state:schemas.MainState) -> dict:
    snapshot = await fetch_quant_snapshot(
        state["ticker"], state["market"], state["as_of_date"]
    )
    summary = await _interpret(state, snapshot)
    return {"quant_snapshot":snapshot,"quant_summary":summary}