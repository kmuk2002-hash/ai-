"""
에이전트 공통 설정: .env에서 API 키를 읽고, 경로 상수를 정의한다.
다른 모듈은 os.getenv를 직접 부르지 말고 여기서 가져다 쓴다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# config.py 위치 기준으로 프로젝트 루트(주식/)를 찾는다.
#   agent/config.py → parents[0]=agent, [1]=backend, [2]=주식
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

load_dotenv(ROOT_DIR / ".env")

# ── API 키
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ── 캐시 (외부 API 응답 저장 위치)
CACHE_DIR = BACKEND_DIR / ".cache"

# ── LLM 모델: 작업 난이도에 따라 두 등급으로 나눈다 (agent/llm.py 참고)
#   OPENAI_MODEL       : heavy. 요약·리포트 작성·과거 비교처럼 긴 문서를 읽고 판단하는 작업
#   OPENAI_MODEL_LIGHT : light. 관련성 yes/no, 검색어 재작성, 숫자 대조처럼 짧은 분류·변환 작업
#   LLM_ROUTING        : tiered(두 모델 나눠 쓰기) | single(모두 heavy) ← 비교 실험용
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_LIGHT = os.getenv("OPENAI_MODEL_LIGHT", "gpt-4.1-nano")
LLM_ROUTING = os.getenv("LLM_ROUTING", "tiered")
# 관련성 검사 방식: v1(LLM이 yes/no 직접) | v2(LLM은 주제별 근거 문서만, yes/no는 코드가)
#   기본 v2: scripts/exp_model_routing.py 실험에서 gpt-4.1-nano + v2가 정확도 0.67로 가장 높았다
#   (gpt-4o-mini + v1은 0.56, 자료가 부족해도 항상 yes)
RELEVANCE_JUDGE = os.getenv("RELEVANCE_JUDGE", "v2")

# ── LLM 제공자: openai(유료 API) | ollama(로컬 무료 모델, 실험용)
#   ollama일 때는 위 OPENAI_MODEL* 대신 아래 두 모델을 heavy/light로 쓴다.
#   준비: ollama serve → ollama pull qwen3:8b → ollama pull qwen2.5:3b
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")                 # heavy
OLLAMA_MODEL_LIGHT = os.getenv("OLLAMA_MODEL_LIGHT", "qwen2.5:3b")   # light
# Ollama 기본 문맥 길이(2048토큰)는 문서 25개를 넣으면 앞부분이 잘린다 → 넉넉히 늘린다
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))

# ── 펀더멘털 웹 검색 방식
#   "fixed": 정해진 검색어로 Tavily를 직접 호출 (빠르고 결과가 일정함)
#   "agent": LLM이 Tavily 툴을 골라 쓰는 ReAct 에이전트 (검색어를 스스로 정함)
# .env의 WEB_SEARCH_MODE로 바꾸거나, 노트북에서 config.WEB_SEARCH_MODE = "agent"로 바꿀 수 있다.
WEB_SEARCH_MODE = os.getenv("WEB_SEARCH_MODE", "fixed")

# ── 검증 노드 (리포트 숫자를 퀀트 데이터와 대조). 켜면 LLM 호출이 1~2회 늘어난다.
VERIFY_ENABLED = os.getenv("VERIFY_ENABLED", "false").lower() in ("1", "true", "yes")

# ── DB (리포트·하이라이트·결정 저장, 과거 결정 조회, RAG 벡터 검색)
#   비어 있으면 DB 없이 동작한다: 과거 결정은 None, 문서 검색은 빈 결과
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://invest:invest@localhost:5432/invest")

# ── RAG
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")   # 1536차원
EMBEDDING_DIM = 1536
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
# SEC EDGAR는 연락처가 들어간 User-Agent가 필수 (예: "Mugyeom Kim you@example.com")
SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT")

# ── 실험 스크립트가 이번 실행에 덧붙이는 태그 (scripts/exp_pipeline.py가 채운다)
RUN_TAGS: list[str] = []

# ── LangSmith 추적
#   LANGSMITH_TRACING=true + LANGSMITH_API_KEY가 있으면 그래프·LLM·외부 호출이 LangSmith에 기록된다.
#   키가 없으면 추적만 꺼지고 나머지는 그대로 동작한다.
def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes")


LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "invest-report-agent"
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")   # 비우면 기본 (https://api.smith.langchain.com)
TRACING_ENABLED = bool(LANGSMITH_API_KEY) and _truthy(
    os.getenv("LANGSMITH_TRACING") or os.getenv("LANGCHAIN_TRACING_V2")
)

# langsmith / langchain 라이브러리는 환경변수를 직접 읽으므로 여기서 정리해 둔다.
os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
os.environ["LANGSMITH_TRACING"] = "true" if TRACING_ENABLED else "false"
os.environ["LANGCHAIN_TRACING_V2"] = "true" if TRACING_ENABLED else "false"
if LANGSMITH_API_KEY:
    os.environ.setdefault("LANGSMITH_API_KEY", LANGSMITH_API_KEY)

def require(name: str, value: str | None) -> str:
    """키가 없으면 어떤 키가 없는지 바로 알 수 있게 에러를 낸다."""
    if not value:
        raise RuntimeError(f"{name}가 설정되지 않았습니다. 프로젝트 루트의 .env를 확인하세요.")
    return value