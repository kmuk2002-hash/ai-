"""
PostgreSQL 연결. 로컬 단일 사용자 앱이라 풀 없이 요청마다 연결한다(로컬에서는 수 ms).
"""

from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row

from agent import config


class DatabaseNotConfigured(RuntimeError):
    pass


@asynccontextmanager
async def connect():
    """async with connect() as conn: ...
    블록이 정상 종료되면 commit, 에러가 나면 rollback 된다."""
    if not config.DATABASE_URL:
        raise DatabaseNotConfigured("DATABASE_URL이 설정되지 않았습니다.")
    conn = await psycopg.AsyncConnection.connect(
        config.DATABASE_URL, row_factory=dict_row, connect_timeout=3
    )
    try:
        async with conn:
            yield conn
    finally:
        if not conn.closed:
            await conn.close()
