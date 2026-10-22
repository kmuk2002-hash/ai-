from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from agent import config
from agent.llm import get_llm
from agent.prompts import fundamental as P
from agent.retrieval import vector_store, web_search
from agent.schemas import FundamentalState, FundamentalSummary, Source

MAX_RETRY = 2            # 재검색 최대 횟수
MAX_DOCS = 30            # LLM에 넘길 최대 문서 수
DOC_CHARS = 800          # 문서 하나당 LLM에 넘길 최대 글자 수
AGENT_MAX_SEARCHES = 4   # 에이전트 방식의 최대 검색 횟수


# ─────────────────────────────────────────────
# 문서 → 프롬프트용 텍스트
# ─────────────────────────────────────────────


def _format_docs(docs: list[Document]) -> str:
    """[번호] 제목 (URL) + 본문 앞부분. 번호는 요약 노드가 출처를 고를 때 쓴다."""
    if not docs:
        return "(문서 없음)"
    blocks = []
    for i, d in enumerate(docs):
        body = d.page_content[:DOC_CHARS]
        blocks.append(f"[{i}] {d.metadata.get('title', '')} ({d.metadata.get('url', '')})\n{body}")
    return "\n\n".join(blocks)


# ─────────────────────────────────────────────
# 검색 노드
# ─────────────────────────────────────────────


# 처음 검색할 때 10-K 섹션별로 던질 질문
_SECTION_QUERIES = [
    ("Item 1", "business model, products and services, revenue segments, competition"),
    ("Item 1A", "most significant risk factors"),
    ("Item 7", "management discussion of results, outlook, liquidity and key trends"),
]


async def search_documents(state: FundamentalState) -> dict:
    """적재된 10-K(pgvector)에서 검색. 적재 전이거나 DB가 없으면 빈 결과."""
    common = dict(ticker=state["ticker"], market=state["market"], as_of=state["as_of_date"])
    docs: list[Document] = []
    if state["retry_count"] == 0:
        for section, q in _SECTION_QUERIES:
            docs += await vector_store.search(f"{state['ticker']} {q}", section=section, **common)
    else:
        docs += await vector_store.search(state["question"], **common)
    return {"vector_docs": docs}


async def search_web(state: FundamentalState) -> dict:
    """config.WEB_SEARCH_MODE에 따라 두 방식 중 하나로 검색한다."""
    ticker, as_of = state["ticker"], state["as_of_date"]
    first_try = state["retry_count"] == 0

    if config.WEB_SEARCH_MODE == "agent":
        docs = await web_search.search_with_agent(
            system_prompt=P.AGENT_SYSTEM.format(as_of_date=as_of, max_searches=AGENT_MAX_SEARCHES),
            task=P.AGENT_TASK.format(ticker=ticker, question=state["question"]),
            max_searches=AGENT_MAX_SEARCHES,
        )
    else:
        # 처음에는 정해진 검색어 4개, 재검색 때는 query_rewrite가 만든 검색어 하나
        queries = (
            [(q.format(ticker=ticker), days) for q, days in P.FIXED_QUERIES]
            if first_try
            else [(state["question"], None)]
        )
        docs = await web_search.search_fixed(queries, as_of)

    return {"web_docs": docs}


async def unify_documents(state: FundamentalState) -> dict:
    """이전에 모은 문서 + 이번 검색 결과를 합치고 중복을 없앤다.
    재검색해도 앞에서 찾은 문서는 버리지 않고 쌓는다."""
    merged, seen = [], set()
    for d in state["context"] + state["vector_docs"] + state["web_docs"]:
        # 10-K 조각들은 URL이 같으므로 URL + 본문 앞부분으로 구분한다
        key = (d.metadata.get("url"), d.page_content[:200])
        if key not in seen:
            seen.add(key)
            merged.append(d)
    return {"context": merged[:MAX_DOCS]}


# ─────────────────────────────────────────────
# 관련성 검사 → (부족하면) 검색어 재작성
# ─────────────────────────────────────────────


class _Relevance(BaseModel):
    relevant: Literal["yes", "no"] = Field(description="네 주제 중 셋 이상을 문서로 뒷받침할 수 있으면 yes")
    missing: str = Field(default="", description="no일 때 부족한 주제")


class _Coverage(BaseModel):
    """[v2] LLM은 주제마다 그 주제를 직접 다루는 문서 번호만 고른다. yes/no는 코드가 정한다."""

    business_docs: list[int] = Field(default_factory=list, description="사업 구조·경쟁 환경을 직접 다루는 문서 번호")
    risk_docs: list[int] = Field(default_factory=list, description="회사가 밝힌 리스크를 직접 다루는 문서 번호")
    outlook_docs: list[int] = Field(default_factory=list, description="경영진 전망·가이던스·애널리스트 기대를 다루는 문서 번호")
    news_docs: list[int] = Field(default_factory=list, description="최근 뉴스·이슈를 다루는 문서 번호")


_TOPIC_FIELDS = [("business_docs", "사업 구조와 경쟁 환경"), ("risk_docs", "회사가 밝힌 리스크"),
                 ("outlook_docs", "경영진 전망·가이던스"), ("news_docs", "최근 이슈")]


def decide_relevance(cov: _Coverage, n_docs: int) -> _Relevance:
    """권위 게이트: 실제로 있는 문서 번호만 인정하고, 근거가 있는 주제가 3개 이상이면 yes."""
    covered = [name for field, name in _TOPIC_FIELDS
               if any(0 <= i < n_docs for i in getattr(cov, field))]
    missing = [name for _, name in _TOPIC_FIELDS if name not in covered]
    return _Relevance(relevant="yes" if len(covered) >= 3 else "no", missing=", ".join(missing))


async def relevance_check(state: FundamentalState) -> dict:
    docs = _format_docs(state["context"])
    human = P.RELEVANCE_HUMAN.format(ticker=state["ticker"], docs=docs)
    if config.RELEVANCE_JUDGE == "v2":
        cov: _Coverage = await get_llm(temperature=0, tier="light").with_structured_output(_Coverage).ainvoke(
            [("system", P.COVERAGE_SYSTEM), ("human", human)]
        )
        result = decide_relevance(cov, len(state["context"]))
    else:
        llm = get_llm(temperature=0, tier="light").with_structured_output(_Relevance)
        result: _Relevance = await llm.ainvoke([("system", P.RELEVANCE_SYSTEM), ("human", human)])
    update = {"relevance": result.relevant}
    if result.relevant == "no" and result.missing:
        update["question"] = result.missing     # 무엇이 부족한지를 다음 단계(재작성)에 넘긴다
    return update


async def query_rewrite(state: FundamentalState) -> dict:
    titles = "\n".join(f"- {d.metadata.get('title', '')}" for d in state["context"]) or "(없음)"
    response = await get_llm(temperature=0, tier="light").ainvoke([
        ("system", P.REWRITE_SYSTEM),
        ("human", P.REWRITE_HUMAN.format(ticker=state["ticker"], question=state["question"], titles=titles)),
    ])
    return {
        "question": response.content.strip().strip('"'),
        "retry_count": state["retry_count"] + 1,
    }


def route_relevance(state: FundamentalState) -> str:
    if state["relevance"] == "yes" or state["retry_count"] >= MAX_RETRY:
        return "relevance"
    return "no_relevance"


# ─────────────────────────────────────────────
# 요약
# ─────────────────────────────────────────────


class _SummaryBody(BaseModel):
    """LLM이 채우는 부분. 출처는 used_doc_ids로 코드에서 만든다."""

    business_overview: str = Field(description="사업 구조, 주요 제품과 매출원, 경쟁 환경")
    stated_risks: str = Field(description="회사가 밝힌 주요 리스크")
    management_outlook: str = Field(description="경영진의 실적 해석과 전망, 가이던스, 애널리스트 기대")
    recent_issues: str = Field(description="최근 뉴스와 이슈")
    used_doc_ids: list[int] = Field(description="요약에 실제로 사용한 문서 번호")


def _sources(docs: list[Document], ids: list[int]) -> list[Source]:
    out, seen = [], set()
    for i in dict.fromkeys(ids):            # 순서 유지하며 중복 제거
        if 0 <= i < len(docs):              # LLM이 없는 번호를 말해도 무시
            m = docs[i].metadata
            key = (m.get("url"), m.get("section"))   # 같은 10-K 섹션의 여러 조각은 출처 1개로
            if key in seen:
                continue
            seen.add(key)
            out.append(Source(
                title=m.get("title") or m.get("url", ""),
                url=m.get("url"),
                doc_type=m.get("doc_type", "web"),
                section=m.get("section"),
            ))
    return out


async def make_fundamental_summary(state: FundamentalState) -> dict:
    docs = state["context"]
    llm = get_llm().with_structured_output(_SummaryBody)
    body: _SummaryBody = await llm.ainvoke([
        ("system", P.SUMMARY_SYSTEM),
        ("human", P.SUMMARY_HUMAN.format(
            ticker=state["ticker"], as_of_date=state["as_of_date"], docs=_format_docs(docs),
        )),
    ])
    summary = FundamentalSummary(
        **body.model_dump(exclude={"used_doc_ids"}),
        sources=_sources(docs, body.used_doc_ids),
    )
    return {"summary": summary}
