"""
Tavily MCP로 웹 검색을 하고, 결과를 LangChain Document로 바꾼다.

두 가지 방식을 제공한다.
  search_fixed()      : 정해진 검색어 목록으로 툴을 직접 호출 (워크플로우)
  search_with_agent() : LLM이 Tavily 툴을 골라 쓰는 ReAct 에이전트 (에이전트)

어느 방식이든 결과는 같은 형태(list[Document])라서, 서브그래프는 방식을 몰라도 된다.
Document.metadata에 title, url, query를 담아 두고, 출처는 나중에 이 값으로 코드에서 만든다.
"""

import json
from datetime import date
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from agent import mcp_client
from agent.llm import get_llm
from agent.tracing import annotate, traced

SERVER = "tavily"
# 서버 버전에 따라 툴 이름이 tavily_search 또는 tavily-search
_SEARCH_TOOL_NAMES = ("tavily_search", "tavily-search")


# ─────────────────────────────────────────────
# 공통: 툴 이름 찾기, 응답 파싱
# ─────────────────────────────────────────────


async def _search_tool():
    """Tavily 서버의 검색 툴(LangChain 툴 객체)을 찾는다. 툴 목록은 mcp_client가 캐싱한다."""
    tools = await mcp_client.get_tools(SERVER)
    for t in tools:
        if t.name in _SEARCH_TOOL_NAMES:
            return t
    raise RuntimeError(f"[Tavily] 검색 툴을 찾을 수 없습니다. 받은 툴: {[t.name for t in tools]}")


def parse_tavily_text(text: str, query: str = "") -> list[Document]:
    """Tavily MCP 응답을 Document 목록으로 바꾼다.

    실제 서버는 Tavily API 응답 JSON을 그대로 보낸다. (문서에는 텍스트 형식으로 나와 있었음)
        {"query": ..., "answer": ..., "results": [{"url", "title", "content", "score", "published_date"?}, ...]}
    JSON이 아니면 문서에 적힌 텍스트 형식(Title:/URL:/Content:)으로 읽는다.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return _parse_text_format(text, query)

    if not isinstance(data, dict):
        return []
    docs: list[Document] = []
    for r in data.get("results") or []:
        url = r.get("url")
        if not url:
            continue
        docs.append(Document(
            page_content=(r.get("content") or "").strip(),
            metadata={
                "title": r.get("title") or url,
                "url": url,
                "query": query or data.get("query", ""),
                "score": r.get("score"),
                "published_date": r.get("published_date"),
            },
        ))
    return docs


def _parse_text_format(text: str, query: str = "") -> list[Document]:
    """(대비용) 텍스트 형식 응답을 Document 목록으로 바꾼다.

    응답 형식:
        Detailed Results:

        Title: ...
        URL: https://...
        Content: ...

        Title: ...
    """
    docs: list[Document] = []
    cur: dict[str, Any] | None = None
    field: str | None = None

    def flush():
        if cur and cur.get("url"):
            docs.append(Document(
                page_content=cur.get("content", "").strip(),
                metadata={"title": cur.get("title") or cur["url"], "url": cur["url"], "query": query},
            ))

    for line in text.splitlines():
        if line.startswith("Images:"):
            break                                   # 이미지 목록부터는 필요 없음
        if line.startswith("Title: "):
            flush()
            cur, field = {"title": line[7:].strip()}, None
        elif line.startswith("URL: "):
            if cur is None or cur.get("url"):       # 제목 없이 URL부터 시작하는 결과
                flush()
                cur = {}
            cur["url"], field = line[5:].strip(), None
        elif line.startswith("Content: ") and cur is not None:
            cur["content"], field = line[9:], "content"
        elif line.startswith(("Raw Content: ", "Favicon: ", "ID: ")):
            field = None
        elif field == "content" and cur is not None:
            cur["content"] += "\n" + line           # 여러 줄로 된 본문 이어 붙이기
    flush()
    return docs


def _date_args(as_of: date, recent_days: int | None = None) -> dict:
    """as_of_date 이후의 글은 검색하지 않는다(미래 정보 누수 방지). recent_days가 있으면 최근 글만."""
    args = {"end_date": as_of.isoformat()}
    if recent_days:
        args["start_date"] = date.fromordinal(as_of.toordinal() - recent_days).isoformat()
    return args


def _dedupe(docs: list[Document]) -> list[Document]:
    seen, out = set(), []
    for d in docs:
        url = d.metadata.get("url")
        if url and url not in seen:
            seen.add(url)
            out.append(d)
    return out


# ─────────────────────────────────────────────
# 방식 A: 정해진 검색어로 직접 호출
# ─────────────────────────────────────────────


def _docs_summary(docs) -> dict:
    return {"doc_count": len(docs), "titles": [d.metadata.get("title") for d in docs[:10]]}


@traced("tavily.search_fixed", run_type="retriever", process_outputs=_docs_summary)
async def search_fixed(
    queries: list[tuple[str, int | None]], as_of: date, max_results: int = 5
) -> list[Document]:
    """queries: [(검색어, 최근 며칠만 볼지 또는 None), ...]
    세션 하나를 열어 검색어를 차례로 호출한다."""
    tool = (await _search_tool()).name
    annotate(query_count=len(queries))
    docs: list[Document] = []

    async with mcp_client.session(SERVER) as s:
        for q, recent_days in queries:
            args = {"query": q, "max_results": max_results, **_date_args(as_of, recent_days)}
            text = await mcp_client.call_text(s, tool, args)
            docs.extend(parse_tavily_text(text, query=q))

    return _dedupe(docs)


# ─────────────────────────────────────────────
# 방식 B: ReAct 에이전트
# ─────────────────────────────────────────────


def _text_of(content: Any) -> str:
    """ToolMessage.content는 문자열이거나 [{'type': 'text', 'text': ...}] 목록이다."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "") for c in content
        )
    return str(content)


@traced("tavily.search_with_agent", run_type="chain", process_outputs=_docs_summary)
async def search_with_agent(
    system_prompt: str, task: str, max_searches: int = 4
) -> list[Document]:
    """LLM에게 Tavily 검색 툴을 주고, 무엇을 몇 번 검색할지 스스로 정하게 한다.

    에이전트가 쓴 최종 답변은 버리고, 툴이 돌려준 검색 결과(ToolMessage)만 모은다.
    → 요약은 서브그래프의 요약 노드가 한다. 에이전트는 '자료 수집'만 담당.
    """
    tool = await _search_tool()
    agent = create_react_agent(get_llm(), [tool], prompt=system_prompt)

    # 툴 1회 = LLM 호출 + 툴 실행 2단계. 최대 검색 횟수를 넘으면 강제로 멈춘다.
    config = {"recursion_limit": 2 * max_searches + 1}
    docs: list[Document] = []
    queries: dict[str, str] = {}   # tool_call_id → 에이전트가 정한 검색어

    try:
        async for update in agent.astream({"messages": [("user", task)]}, config, stream_mode="updates"):
            for node_output in update.values():
                for msg in node_output.get("messages", []):
                    for call in getattr(msg, "tool_calls", None) or []:   # LLM이 툴을 부르기로 한 메시지
                        queries[call["id"]] = call["args"].get("query", "")
                    if isinstance(msg, ToolMessage):                       # 툴 실행 결과
                        query = queries.get(msg.tool_call_id, "")
                        docs.extend(parse_tavily_text(_text_of(msg.content), query=query))
    except GraphRecursionError:
        pass  # 검색 횟수 한도에 닿음. 그때까지 모은 결과를 쓴다.

    annotate(query_count=len(queries), queries=list(queries.values()))
    return _dedupe(docs)
