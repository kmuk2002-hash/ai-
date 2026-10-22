-- ============================================================
-- RAG: 10-K 문서 조각 + 임베딩 (pgvector)
-- docker-compose가 처음 DB를 만들 때 자동 적용된다.
-- 이미 DB를 만든 뒤라면: docker exec -i invest-db psql -U invest invest < db/rag.sql
-- (ingestion.load도 시작할 때 이 파일을 실행하므로 따로 안 해도 된다)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunk (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    market        TEXT        NOT NULL CHECK (market IN ('US', 'KR')),
    ticker        TEXT        NOT NULL,
    doc_type      TEXT        NOT NULL,          -- '10-K'
    section       TEXT        NOT NULL,          -- 'Item 1' / 'Item 1A' / 'Item 7'
    title         TEXT        NOT NULL,          -- 'AAPL 10-K (FY2025) Item 1A'
    url           TEXT,
    published_at  DATE        NOT NULL,          -- 공시일 (as_of_date 이후 문서는 검색에서 제외)
    chunk_index   INTEGER     NOT NULL,
    content       TEXT        NOT NULL,
    embedding     vector(1536) NOT NULL,         -- text-embedding-3-small
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticker, doc_type, url, section, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunk_filter
    ON document_chunk (market, ticker, published_at);

CREATE INDEX IF NOT EXISTS idx_chunk_embedding
    ON document_chunk USING hnsw (embedding vector_cosine_ops);
