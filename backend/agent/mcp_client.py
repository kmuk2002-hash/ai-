import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession

from agent import config
from agent.tracing import traced

# 세션을 닫을 때 서버가 종료 요청(DELETE)을 지원하지 않으면
# "Session termination failed: 501" 경고가 찍힌다. 동작에는 영향이 없어서 숨긴다.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

def _connections() -> dict:
    """서버 별명 → 접속 정보. 서버를 추가할 때는 여기에 한 항목만 추가한다."""
    conns = {}
    if config.ALPHAVANTAGE_API_KEY:
        conns["alphavantage"] = {
            "transport": "streamable_http",
            "url": f"https://mcp.alphavantage.co/mcp?apikey={config.ALPHAVANTAGE_API_KEY}",
        }
    if config.TAVILY_API_KEY:
        conns["tavily"] = {
            "transport": "streamable_http",
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={config.TAVILY_API_KEY}",
        }
    return conns

#클라이언트가 접속할 서버 정보
client = MultiServerMCPClient(_connections())

_tool_cache: dict[str,list[BaseTool]] = {}

def _check_server(server : str) -> None:
    if server not in client.connections:
        raise RuntimeError(
            f"MCP 서버 '{server}'가 설정되지 않았습니다. .env에 해당 API키가 있는지 확인하세요."
        )

async def get_tools(server: str) -> list[BaseTool]:
    _check_server(server)
    if server not in _tool_cache:
        _tool_cache[server] = await client.get_tools(server_name = server)

    return _tool_cache[server]

@asynccontextmanager
async def session(server: str):
    _check_server(server)
    try:
        async with client.session(server) as s:
            yield s

    except BaseException as e:
        root = _unwrap(e)
        if root is e:          # 묶음이 아니면 받은 그대로
            raise
        raise root from None   # 묶음이었으면 안의 원래 에러를 던짐


def _unwrap(e: BaseException) -> BaseException:
    """ExceptionGroup이 여러 겹으로 감싸져 있어도, 에러가 하나뿐이면 끝까지 벗겨서 꺼낸다."""
    while True:
        inner = getattr(e, "exceptions", None)
        if inner and len(inner) == 1:
            e = inner[0]
        else:
            return e

def _mcp_inputs(inputs: dict) -> dict:
    """추적 기록용: 세션 객체는 빼고 툴 이름과 인자만 남긴다(API 키는 인자에 없음)."""
    return {"tool": inputs.get("tool"), "args": inputs.get("args")}


@traced("mcp.call_text", process_inputs=_mcp_inputs, process_outputs=lambda o: {"chars": len(o) if isinstance(o, str) else None})
async def call_text(s: ClientSession, tool: str, args: dict[str, Any]) -> str:
    """툴을 호출하고 텍스트 응답을 그대로 반환한다. (Tavily처럼 JSON이 아닌 글로 답하는 툴용)"""
    result = await s.call_tool(tool, args)
    text = "".join(c.text for c in result.content if getattr(c, "type", None) == "text")
    if result.isError:
        raise RuntimeError(f"[MCP] {tool} 호출 실패: {text[:300]}")
    return text


@traced("mcp.call_json", process_inputs=_mcp_inputs, process_outputs=lambda o: {"type": type(o).__name__, "keys": list(o)[:10] if isinstance(o, dict) else None})
async def call_json(s: ClientSession, tool: str, args: dict[str, Any]) -> Any:
    """툴을 호출하고, 텍스트 응답을 JSON으로 바꿔 반환한다."""
    text = await call_text(s, tool, args)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"[MCP] {tool} 응답이 JSON이 아닙니다. 앞부분: {text[:300]!r}"
        ) from e
