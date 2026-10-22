"""
LangSmith 추적 설정.

- run_config(): 분석 1회에 붙일 RunnableConfig (run_name, tags, metadata)
  → LangSmith에서 종목·검색 방식·검증 여부·과거 기록 여부·캐시 상태로 필터해 Before/After를 비교할 수 있다.
- traced(): LangChain이 아닌 작업(MCP 호출, DB 조회, 벡터 검색 등)을 LangSmith span으로 남기는 데코레이터.
  추적이 꺼져 있으면 함수를 그대로 실행한다(반환값도 그대로).
- annotate(): 지금 실행 중인 span에 메타데이터를 덧붙인다(예: 캐시 적중 여부). 추적이 꺼져 있으면 아무것도 안 한다.

LangGraph 노드와 LLM 호출은 LangChain이 자동으로 추적한다.
"""

from datetime import date
from typing import Any, Callable

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from agent import config
from agent.llm import model_for


def traced(name: str, run_type: str = "tool", **kwargs) -> Callable:
    return traceable(name=name, run_type=run_type, **kwargs)


def annotate(**metadata: Any) -> None:
    rt = get_current_run_tree()
    if rt is not None:
        rt.add_metadata(metadata)


def run_config(
    ticker: str,
    market: str,
    as_of_date: date,
    *,
    has_past: bool | None = None,
    cache_warm: bool | None = None,
    source: str = "api",
    verify_enabled: bool | None = None,
) -> dict:
    """그래프 ainvoke(..., config=run_config(...))에 넘길 설정."""
    verify = config.VERIFY_ENABLED if verify_enabled is None else verify_enabled
    tags = [
        f"market:{market}",
        f"web:{config.WEB_SEARCH_MODE}",
        f"verify:{'on' if verify else 'off'}",
        f"source:{source}",
        f"llm:{config.LLM_ROUTING}",
        f"provider:{config.LLM_PROVIDER}",
        *config.RUN_TAGS,
    ]
    if has_past is not None:
        tags.append("has_past" if has_past else "no_past")
    if cache_warm is not None:
        tags.append(f"av_cache:{'warm' if cache_warm else 'cold'}")
    return {
        "run_name": f"analyze:{ticker.upper()}",
        "tags": tags,
        "metadata": {
            "ticker": ticker.upper(),
            "market": market,
            "as_of_date": as_of_date.isoformat(),
            "model": model_for("heavy"),
            "model_light": model_for("light"),
            "llm_routing": config.LLM_ROUTING,
            "web_search_mode": config.WEB_SEARCH_MODE,
            "verify_enabled": verify,
            "has_past": has_past,
            "av_cache_warm": cache_warm,
            "source": source,
        },
    }
