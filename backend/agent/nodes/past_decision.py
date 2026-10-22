import logging

from agent import config, schemas

log = logging.getLogger(__name__)

# 노트북 테스트용: 여기에 PastDecision을 넣어 두면 DB 대신 이 값을 쓴다.
#   import agent.nodes.past_decision as pd; pd.TEST_PAST_DECISION = ...
TEST_PAST_DECISION: schemas.PastDecision | None = None


async def past_decision(state: schemas.MainState) -> dict:
    """DB에서 해당 종목의 최신 결정을 조회 → PastDecision 또는 None.
    DB가 없거나 꺼져 있어도 그래프는 계속 돌아야 하므로 None으로 넘어간다."""
    if TEST_PAST_DECISION is not None:
        return {"past_decision": TEST_PAST_DECISION}
    if not config.DATABASE_URL:
        return {"past_decision": None}

    from storage.repositories.decision_repo import get_past_decision   # agent → storage 의존은 여기서만

    try:
        past = await get_past_decision(state["ticker"], state["market"])
    except Exception as e:  # DB 연결 실패 등
        log.warning("과거 결정 조회 실패, 과거 기록 없이 진행합니다: %s", e)
        past = None
    return {"past_decision": past}
