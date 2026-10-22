"""
LLM 생성. 작업 난이도에 따라 두 등급의 모델을 쓴다 (모델 라우팅, W10).

  heavy : 긴 문서를 읽고 판단·작성하는 작업 → 펀더멘털 요약, 퀀트 해석, 리포트 작성, 과거 결정 비교, 검색 에이전트
  light : 짧은 분류·변환 작업 → 관련성 yes/no, 검색어 재작성, 숫자 대조(verify)

config.LLM_ROUTING = "single"이면 모든 노드가 heavy 모델을 쓴다 (비교 실험의 Before).
config.LLM_PROVIDER = "ollama"이면 같은 구조를 로컬 무료 모델로 돌린다 (비용 없이 실험).
"""

from functools import lru_cache
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from agent import config

Tier = Literal["heavy", "light"]


def model_for(tier: Tier) -> str:
    """'제공자:모델' 문자열. 예) openai:gpt-4o-mini, ollama:qwen2.5:3b"""
    light = tier == "light" and config.LLM_ROUTING == "tiered"
    if config.LLM_PROVIDER == "ollama":
        return "ollama:" + (config.OLLAMA_MODEL_LIGHT if light else config.OLLAMA_MODEL)
    return "openai:" + (config.OPENAI_MODEL_LIGHT if light else config.OPENAI_MODEL)


def get_llm(temperature: float = 0.2, tier: Tier = "heavy") -> BaseChatModel:
    # 모델 이름까지 캐시 키에 넣는다 → 실행 중에 설정을 바꿔도 맞는 모델이 나온다
    return build_chat(model_for(tier), temperature)


@lru_cache
def build_chat(spec: str, temperature: float = 0.0, max_tokens: int | None = None) -> BaseChatModel:
    """'제공자:모델' → 채팅 모델. 제공자를 생략하면 openai. 실험 스크립트도 이 함수를 쓴다.
    max_tokens: 출력 길이 상한. 작은 모델이 JSON 목록을 끝없이 이어 쓰는 것을 막는다."""
    provider, _, model = spec.partition(":")
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        kwargs = {}
        if model.startswith("qwen3"):
            kwargs["reasoning"] = False   # qwen3의 생각(think) 출력을 끈다 → 다른 모델과 같은 조건
        return ChatOllama(
            model=model, temperature=temperature,
            base_url=config.OLLAMA_BASE_URL, num_ctx=config.OLLAMA_NUM_CTX,
            num_predict=max_tokens, **kwargs,
        )

    from langchain_openai import ChatOpenAI

    if provider != "openai":          # 'gpt-4o-mini'처럼 제공자 없이 쓴 경우
        model = spec
    return ChatOpenAI(
        model=model,
        api_key=config.require("OPENAI_API_KEY", config.OPENAI_API_KEY),
        temperature=temperature,
        max_tokens=max_tokens,
    )
