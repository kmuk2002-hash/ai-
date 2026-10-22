"""
pgvector에서 10-K 문서 조각을 검색한다. (적재는 ingestion/load.py)

필터: 같은 시장·종목이고, as_of_date 이전에 공시된 문서만 (미래 정보 누수 방지)
"""

import logging
from datetime import date

from langchain_core.documents import Document

from agent import config
from agent.retrieval.embeddings import get_embeddings, to_pgvector
from agent.tracing import traced

log = logging.getLogger(__name__)


@traced(
    "rag.vector_search", run_type="retriever",
    process_outputs=lambda docs: {"doc_count": len(docs), "sections": [d.metadata.get("section") for d in docs]},
)
async def search(
    query: str, *, ticker: str, market: str, as_of: date,
    section: str | None = None, k: int | None = None,
) -> list[Document]:
    """DB가 없거나 적재된 문서가 없으면 빈 목록. 에러로 그래프를 멈추지 않는다."""
    if not config.DATABASE_URL:
        return []
    from storage.connection import connect

    try:
        vec = to_pgvector(await get_embeddings().aembed_query(query))
        sql = """SELECT title, url, section, doc_type, published_at, content,
                        embedding <=> %(vec)s::vector AS distance
                 FROM document_chunk
                 WHERE market = %(market)s AND ticker = %(ticker)s AND published_at <= %(as_of)s"""
        params = {"vec": vec, "market": market, "ticker": ticker.upper(), "as_of": as_of}
        if section:
            sql += " AND section = %(section)s"
            params["section"] = section
        sql += " ORDER BY distance LIMIT %(k)s"
        params["k"] = k or config.RAG_TOP_K

        async with connect() as conn:
            cur = await conn.execute(sql, params)
            rows = await cur.fetchall()
    except Exception as e:
        log.warning("벡터 검색 실패, 문서 검색 없이 진행합니다: %s", e)
        return []

    return [
        Document(
            page_content=r["content"],
            metadata={
                "title": r["title"], "url": r["url"], "doc_type": r["doc_type"],
                "section": r["section"], "published_at": r["published_at"].isoformat(),
                "query": query,
            },
        )
        for r in rows
    ]
