"""
decision + decision_evidence 테이블, 그리고 past_decision 노드용 조회.
"""


from agent import config
from agent.schemas import PastDecision
from agent.tracing import traced
from storage.connection import connect

_PAST_DECISION_SQL = (
    (config.ROOT_DIR / "db" / "queries.sql").read_text(encoding="utf-8")
    .replace(":market", "%(market)s")
    .replace(":ticker", "%(ticker)s")
)

_SELECT = """SELECT d.id, d.ticker, d.market, d.report_id, d.decided_at, d.action, d.weight,
                    d.confidence, d.my_thesis, d.my_thesis_breaker,
                    COALESCE(array_agg(e.highlight_group_id) FILTER (WHERE e.highlight_group_id IS NOT NULL),
                             '{}') AS evidence_group_ids
             FROM decision d
             LEFT JOIN decision_evidence e ON e.decision_id = d.id"""


def _row(r: dict) -> dict:
    r = dict(r)
    r["weight"] = float(r["weight"]) if r["weight"] is not None else None
    r["evidence_group_ids"] = [str(x) for x in r["evidence_group_ids"]]
    return r


async def create_decision(
    *, report_id: str, ticker: str, market: str, action: str, weight: float | None,
    confidence: int, my_thesis: str, my_thesis_breaker: str, evidence_group_ids: list[str],
) -> dict:
    async with connect() as conn:
        cur = await conn.execute(
            """INSERT INTO decision (report_id, ticker, market, action, weight, confidence,
                                     my_thesis, my_thesis_breaker)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (report_id, ticker.upper(), market, action, weight, confidence, my_thesis, my_thesis_breaker),
        )
        decision_id = (await cur.fetchone())["id"]
        for gid in evidence_group_ids:
            await conn.execute(
                "INSERT INTO decision_evidence (decision_id, highlight_group_id) VALUES (%s, %s)",
                (decision_id, gid),
            )
        cur = await conn.execute(_SELECT + " WHERE d.id = %s GROUP BY d.id", (decision_id,))
        return _row(await cur.fetchone())


async def list_all_decisions() -> list[dict]:
    """전체 결정, 최신순"""
    async with connect() as conn:
        cur = await conn.execute(_SELECT + " GROUP BY d.id ORDER BY d.decided_at DESC")
        return [_row(r) for r in await cur.fetchall()]


async def list_decisions(ticker: str, market: str | None = None) -> list[dict]:
    """최신순"""
    sql, params = _SELECT + " WHERE d.ticker = %s", [ticker.upper()]
    if market:
        sql += " AND d.market = %s"; params.append(market)
    sql += " GROUP BY d.id ORDER BY d.decided_at DESC"
    async with connect() as conn:
        cur = await conn.execute(sql, params)
        return [_row(r) for r in await cur.fetchall()]


@traced(
    "db.past_decision", run_type="retriever",
    process_outputs=lambda p: {"found": p is not None,
                               "decided_at": p.decision.decided_at.isoformat() if p else None,
                               "highlights": len(p.highlights) if p else 0},
)
async def get_past_decision(ticker: str, market: str) -> PastDecision | None:
    """종목의 최신 결정 1건 + 그때 리포트 + 하이라이트 (db/queries.sql). 없으면 None."""
    async with connect() as conn:
        cur = await conn.execute(_PAST_DECISION_SQL, {"ticker": ticker.upper(), "market": market})
        row = await cur.fetchone()
    return PastDecision.model_validate(row["past_decision"]) if row else None
