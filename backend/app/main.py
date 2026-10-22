"""
FastAPI 서버.

    cd backend
    uvicorn app.main:app --reload --port 8000

API 문서: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import setup_logging
from agent.graph import build_graph
from app.routers import analyze, decisions, highlights, reports
from storage.connection import DatabaseNotConfigured


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버가 시작될 때 그래프를 한 번만 컴파일해서 재사용한다.
    app.state.agent = build_graph()
    yield


app = FastAPI(title="투자 의사결정 노트 API", lifespan=lifespan)

app.include_router(analyze.router)
app.include_router(reports.router)
app.include_router(highlights.router)
app.include_router(decisions.router)


@app.exception_handler(psycopg.OperationalError)
@app.exception_handler(DatabaseNotConfigured)
async def db_unavailable(request: Request, exc: Exception):
    return JSONResponse(
        status_code=503,
        content={"detail": "DB에 연결할 수 없습니다. `docker compose up -d`로 PostgreSQL을 켰는지 확인하세요."},
    )


@app.exception_handler(psycopg.errors.InvalidTextRepresentation)
async def bad_id(request: Request, exc: Exception):
    return JSONResponse(status_code=404, content={"detail": "잘못된 ID입니다."})


@app.get("/health")
async def health():
    return {"status": "ok"}
