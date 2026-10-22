-- ============================================================
-- past_decision 노드용 조회 쿼리
-- 결과 JSON이 agent/schemas.py 의 PastDecision 구조와 같으므로
--   PastDecision.model_validate(row["past_decision"]) 로 바로 변환 가능
-- 과거 결정이 없으면 0행 → past_decision = None
--
-- 파라미터: :market, :ticker  (psycopg에서는 %(market)s, %(ticker)s)
-- ============================================================

WITH latest AS (
    SELECT *
    FROM decision
    WHERE market = :market AND ticker = :ticker
    ORDER BY decided_at DESC
    LIMIT 1
)
SELECT jsonb_build_object(
    'decision', jsonb_build_object(
        'ticker',            l.ticker,
        'market',            l.market,
        'decided_at',        l.decided_at,
        'action',            l.action,
        'weight',            l.weight,
        'confidence',        l.confidence,
        'my_thesis',         l.my_thesis,
        'my_thesis_breaker', l.my_thesis_breaker
    ),
    'report', jsonb_build_object(
        'ticker',               r.ticker,
        'market',               r.market,
        'as_of_date',           r.as_of_date,
        'quant_snapshot',       r.quant_snapshot,
        'investment_thesis',    r.investment_thesis,
        'risks',                r.risks,
        'consensus_gap',        r.consensus_gap,
        'thesis_breakers',      r.thesis_breakers,
        'past_decision_review', r.past_decision_review,
        'sources',              r.sources
    ),
    'highlights', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id',         g.id,
            'tag',        g.tag,
            'comment',    g.comment,
            'created_at', g.created_at,
            'spans', (
                SELECT jsonb_agg(jsonb_build_object(
                    'field',        s.field,
                    'start_offset', s.start_offset,
                    'end_offset',   s.end_offset,
                    'quoted_text',  s.quoted_text
                ) ORDER BY s.field, s.start_offset)
                FROM highlight_span s
                WHERE s.group_id = g.id
            )
        ) ORDER BY g.created_at)
        FROM highlight_group g
        WHERE g.report_id = r.id
    ), '[]'::jsonb),
    'evidence_group_ids', COALESCE((
        SELECT jsonb_agg(e.highlight_group_id)
        FROM decision_evidence e
        WHERE e.decision_id = l.id
    ), '[]'::jsonb)
) AS past_decision
FROM latest l
JOIN report r ON r.id = l.report_id;
