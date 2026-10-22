"""
highlight_group + highlight_span 테이블. 드래그 1회 = 그룹 1개, 섹션마다 조각 1개.
"""

from agent.schemas import HighlightSpan
from storage.connection import connect


async def create_group(report_id: str, tag: str, comment: str | None, spans: list[HighlightSpan]) -> dict:
    async with connect() as conn:
        cur = await conn.execute(
            "INSERT INTO highlight_group (report_id, tag, comment) VALUES (%s, %s, %s) "
            "RETURNING id, tag, comment, created_at",
            (report_id, tag, comment),
        )
        group = await cur.fetchone()
        for s in spans:
            await conn.execute(
                "INSERT INTO highlight_span (group_id, field, start_offset, end_offset, quoted_text) "
                "VALUES (%s, %s, %s, %s, %s)",
                (group["id"], s.field, s.start_offset, s.end_offset, s.quoted_text),
            )
    return {**group, "spans": [s.model_dump() for s in spans]}


async def list_groups(report_id: str) -> list[dict]:
    async with connect() as conn:
        cur = await conn.execute(
            """SELECT g.id, g.tag, g.comment, g.created_at,
                      COALESCE(json_agg(json_build_object(
                          'field', s.field, 'start_offset', s.start_offset,
                          'end_offset', s.end_offset, 'quoted_text', s.quoted_text)
                          ORDER BY s.field, s.start_offset) FILTER (WHERE s.id IS NOT NULL), '[]') AS spans
               FROM highlight_group g
               LEFT JOIN highlight_span s ON s.group_id = g.id
               WHERE g.report_id = %s
               GROUP BY g.id
               ORDER BY g.created_at""",
            (report_id,),
        )
        return await cur.fetchall()
