from langgraph.graph import StateGraph, START, END
from agent import config, schemas

from agent.nodes.quant import quant
from agent.nodes.fundamental import fundamental
from agent.nodes.past_decision import past_decision
from agent.nodes.write_report import write_report
from agent.nodes.compare_with_past import compare_with_past
from agent.nodes.verify import verify

def old_exist(state: schemas.MainState) -> dict:
    """합류 지점. 판단은 route가 하므로 바꾸는 값 없음"""
    return {}

def route_past(state: schemas.MainState) -> str:
    return "yes" if state.get("past_decision") is not None else "no"

def build_graph(verify_enabled: bool | None = None):
    """verify_enabled가 None이면 config.VERIFY_ENABLED를 따른다."""
    if verify_enabled is None:
        verify_enabled = config.VERIFY_ENABLED

    builder = StateGraph(schemas.MainState)

    builder.add_node("fundamental", fundamental)
    builder.add_node("quant", quant)
    builder.add_node("write_report", write_report)
    builder.add_node("past_decision", past_decision)
    builder.add_node("old_exist", old_exist)
    builder.add_node("new_vs_old", compare_with_past)
    if verify_enabled:
        builder.add_node("verify", verify)

    # fan-out
    builder.add_edge(START, "fundamental")
    builder.add_edge(START, "quant")
    builder.add_edge(START, "past_decision")

    # fan-in 1: 펀더멘털 + 퀀트 → 리포트 작성
    builder.add_edge(["fundamental", "quant"], "write_report")

    # (선택) 리포트 숫자 검증: write_report → verify
    report_done = "write_report"
    if verify_enabled:
        builder.add_edge("write_report", "verify")
        report_done = "verify"

    # fan-in 2: 리포트 작성(+검증) + 과거 결정 → 과거 기록 확인
    builder.add_edge([report_done, "past_decision"], "old_exist")

    builder.add_conditional_edges(
        "old_exist",
        route_past,
        {"yes": "new_vs_old", "no": END},
    )
    builder.add_edge("new_vs_old", END)

    return builder.compile()