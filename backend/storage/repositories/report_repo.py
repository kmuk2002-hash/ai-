"""
report 테이블. 리포트는 저장 후 수정하지 않는다(DB 트리거로도 막혀 있음).
"""

from psycopg.types.json import Jsonb

from agent.schemas import Report
from storage.connection import connect

_COLUMNS = """id, ticker, market, as_of_date, quant_snapshot, investment_thesis, risks,
              consensus_gap, thesis_breakers, past_decision_review, sources, created_at"""


def _json(model):
    return None if model is None else Jsonb(model.model_dump(mode="json"))


async def save_report(report: Report) -> dict:
    """리포트를 저장하고 API 응답 형태({id, created_at, ...report})로 돌려준다."""
    async with connect() as conn:
        cur = await conn.execute(
            f"""INSERT INTO report (ticker, market, as_of_date, quant_snapshot, investment_thesis,
                    risks, consensus_gap, thesis_breakers, past_decision_review, sources)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}""",
            (
                report.ticker, report.market, report.as_of_date, _json(report.quant_snapshot),
                report.investment_thesis, report.risks, report.consensus_gap, report.thesis_breakers,
                _json(report.past_decision_review),
                Jsonb([s.model_dump(mode="json") for s in report.sources]),
            ),
        )
        return await cur.fetchone()


async def get_report(report_id: str) -> dict | None:
    async with connect() as conn:
        cur = await conn.execute(f"SELECT {_COLUMNS} FROM report WHERE id = %s", (report_id,))
        return await cur.fetchone()


async def list_reports(ticker: str | None = None, market: str | None = None) -> list[dict]:
    """최신순. 파라미터가 없으면 전체."""
    where, params = [], []
    if ticker:
        where.append("ticker = %s"); params.append(ticker.upper())
    if market:
        where.append("market = %s"); params.append(market)
    sql = "SELECT id, ticker, market, as_of_date, created_at FROM report"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    async with connect() as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchall()


# 리포트마다 "그 리포트를 만들기 직전의 최신 결정"을 붙인다 (past_decision 노드가 비교한 바로 그 결정)
_NOTICE_SQL = """
SELECT r.id AS report_id, r.ticker, r.market, r.as_of_date, r.created_at, r.past_decision_review,
       d.id AS decision_id, d.report_id AS decision_report_id, d.action, d.decided_at
FROM report r
JOIN LATERAL (
    SELECT id, report_id, action, decided_at FROM decision
    WHERE ticker = r.ticker AND market = r.market AND decided_at < r.created_at
    ORDER BY decided_at DESC LIMIT 1
) d ON TRUE
WHERE r.past_decision_review IS NOT NULL
ORDER BY r.created_at DESC
LIMIT %s
"""


async def list_notifications(limit: int = 50) -> list[dict]:
    """결정 이후 같은 종목을 다시 분석해 생긴 점검 결과 = 알림.
    철회 조건이 '충족'이면 level=alert, 아니면 info. (프론트 lib/notice.ts와 같은 규칙)"""
    async with connect() as conn:
        cur = await conn.execute(_NOTICE_SQL, (limit,))
        rows = await cur.fetchall()
    out = []
    for r in rows:
        review = r["past_decision_review"] or {}
        triggered = [c for c in review.get("checks", []) if c.get("status") == "triggered"]
        out.append({
            "id": str(r["report_id"]),
            "ticker": r["ticker"], "market": r["market"],
            "decision_id": str(r["decision_id"]), "decision_report_id": str(r["decision_report_id"]),
            "action": r["action"], "decided_at": r["decided_at"],
            "report_id": str(r["report_id"]), "as_of_date": r["as_of_date"], "created_at": r["created_at"],
            "summary": review.get("summary", ""),
            "triggered": triggered,
            "level": "alert" if any(c.get("category") == "thesis_breaker" for c in triggered) else "info",
        })
    return out
