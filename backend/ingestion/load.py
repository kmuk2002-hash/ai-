"""
10-K 적재 스크립트.

    cd backend
    python -m ingestion.load AAPL NVDA

종목마다: EDGAR에서 최신 10-K → Item 1, 1A, 7 추출 → 조각내기 → 임베딩 → pgvector 저장.
같은 10-K를 다시 적재하면 기존 조각을 지우고 새로 넣는다.
"""

import asyncio
import sys

from agent import config
from agent.retrieval.embeddings import get_embeddings, to_pgvector
from ingestion.chunking import chunk_text
from ingestion.edgar import fetch_latest_10k
from storage.connection import connect

BATCH = 64


async def _ensure_schema() -> None:
    sql = (config.ROOT_DIR / "db" / "rag.sql").read_text(encoding="utf-8")
    async with connect() as conn:
        await conn.execute(sql)


async def load_ticker(ticker: str) -> int:
    tenk = await asyncio.to_thread(fetch_latest_10k, ticker)   # 동기 HTTP는 스레드에서
    if not tenk.sections:
        print(f"  {ticker}: Item 1/1A/7을 찾지 못했습니다 ({tenk.url})")
        return 0

    rows = []
    for section, body in tenk.sections.items():
        for i, chunk in enumerate(chunk_text(body)):
            rows.append((section, i, chunk))

    emb = get_embeddings()
    vectors: list[list[float]] = []
    for s in range(0, len(rows), BATCH):
        vectors += await emb.aembed_documents([r[2] for r in rows[s:s + BATCH]])

    async with connect() as conn:
        await conn.execute(
            "DELETE FROM document_chunk WHERE ticker = %s AND doc_type = '10-K' AND url = %s",
            (tenk.ticker, tenk.url),
        )
        for (section, idx, chunk), vec in zip(rows, vectors):
            await conn.execute(
                """INSERT INTO document_chunk (market, ticker, doc_type, section, title, url,
                                               published_at, chunk_index, content, embedding)
                   VALUES ('US', %s, '10-K', %s, %s, %s, %s, %s, %s, %s::vector)""",
                (tenk.ticker, section, f"{tenk.ticker} 10-K (FY{tenk.fiscal_year}) {section}",
                 tenk.url, tenk.filing_date, idx, chunk, to_pgvector(vec)),
            )
    counts = {s: sum(1 for r in rows if r[0] == s) for s in tenk.sections}
    print(f"  {ticker}: 10-K {tenk.filing_date} 공시, 조각 {len(rows)}개 {counts}")
    return len(rows)


async def main(tickers: list[str]) -> None:
    await _ensure_schema()
    for t in tickers:
        try:
            await load_ticker(t)
        except Exception as e:
            print(f"  {t}: 실패 - {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python -m ingestion.load AAPL NVDA")
        sys.exit(1)
    asyncio.run(main([t.upper() for t in sys.argv[1:]]))
