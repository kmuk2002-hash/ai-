from langchain_core.runnables import RunnableConfig

from agent import schemas
from agent.subgraphs.fundamental.graph import build_fundamental_graph

subgraph = build_fundamental_graph()   # 모듈 로드 시 1번만 컴파일


async def fundamental(state: schemas.MainState, config: RunnableConfig) -> dict:
    # ① MainState → FundamentalState 입력 만들기
    inp = {
        "ticker": state["ticker"],
        "market": state["market"],
        "as_of_date": state["as_of_date"],
        "question": f"{state['ticker']} 사업 구조, 주요 리스크, 경영진 전망, 최근 이슈",
        "vector_docs": [],
        "web_docs": [],
        "context": [],
        "retry_count": 0,
        "summary": None,
    }

    # ② 서브그래프 실행 (노드들이 async라서 ainvoke)
    #    config를 넘겨야 부모 그래프의 스트리밍(SSE)·LangSmith 추적에 서브그래프 단계가 이어진다
    result = await subgraph.ainvoke(inp, config=config)

    # ③ 필요한 결과만 MainState 키로 옮겨서 반환
    return {"fundamental_summary": result["summary"]}
