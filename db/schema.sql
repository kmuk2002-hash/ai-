-- ============================================================
-- 투자 의사결정 기록 시스템 DB 스키마 (PostgreSQL 13+)
-- agent/schemas.py 의 Pydantic 모델과 1:1로 대응
-- ============================================================

-- ------------------------------------------------------------
-- report: 에이전트가 생성한 리포트 (저장 후 수정 불가)
--   - quant_snapshot        ← QuantSnapshot (결정 시점 박제)
--   - past_decision_review  ← PastDecisionReview (과거 기록 없으면 NULL)
--   - sources               ← list[Source]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS report (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker                TEXT        NOT NULL,
    market                TEXT        NOT NULL CHECK (market IN ('US', 'KR')),
    as_of_date            DATE        NOT NULL,
    quant_snapshot        JSONB       NOT NULL,
    investment_thesis     TEXT        NOT NULL,
    risks                 TEXT        NOT NULL,
    consensus_gap         TEXT        NOT NULL,
    thesis_breakers       TEXT        NOT NULL,
    past_decision_review  JSONB,
    sources               JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_ticker
    ON report (market, ticker, created_at DESC);

-- 리포트 불변 원칙: UPDATE 차단
--   하이라이트 offset이 어긋나지 않게 하고, 결정 시점의 정보를 박제하기 위함
CREATE OR REPLACE FUNCTION prevent_report_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'report는 저장 후 수정할 수 없습니다. 새 리포트를 생성하세요.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_report_immutable ON report;
CREATE TRIGGER trg_report_immutable
    BEFORE UPDATE ON report
    FOR EACH ROW EXECUTE FUNCTION prevent_report_update();


-- ------------------------------------------------------------
-- highlight_group: 사용자의 하이라이트 1회 (태그·메모는 그룹에 1번)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS highlight_group (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id   UUID        NOT NULL REFERENCES report (id) ON DELETE CASCADE,
    tag         TEXT        NOT NULL CHECK (tag IN ('support', 'concern', 'to_verify', 'disagree')),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_highlight_group_report
    ON highlight_group (report_id);


-- ------------------------------------------------------------
-- highlight_span: 섹션별 하이라이트 조각
--   드래그가 여러 섹션에 걸치면 조각이 여러 개 생기고 같은 group_id를 가짐
--   offset은 해당 섹션 텍스트 기준
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS highlight_span (
    id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id      UUID    NOT NULL REFERENCES highlight_group (id) ON DELETE CASCADE,
    field         TEXT    NOT NULL CHECK (field IN (
                      'investment_thesis', 'risks', 'consensus_gap',
                      'thesis_breakers', 'past_decision_review')),
    start_offset  INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset    INTEGER NOT NULL,
    quoted_text   TEXT    NOT NULL,
    CHECK (end_offset > start_offset)
);

CREATE INDEX IF NOT EXISTS idx_highlight_span_group
    ON highlight_span (group_id);


-- ------------------------------------------------------------
-- decision: 사용자의 투자 결정
--   my_thesis_breaker는 결정할 때마다 이전 값을 이어서 복사
--   → 최신 결정 1건만 조회해도 철회 조건을 알 수 있음
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker             TEXT        NOT NULL,
    market             TEXT        NOT NULL CHECK (market IN ('US', 'KR')),
    report_id          UUID        NOT NULL REFERENCES report (id) ON DELETE RESTRICT,
    decided_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    action             TEXT        NOT NULL CHECK (action IN ('buy', 'hold', 'sell')),
    weight             NUMERIC(5, 4) CHECK (weight IS NULL OR (weight >= 0 AND weight <= 1)),
    confidence         SMALLINT    NOT NULL CHECK (confidence BETWEEN 1 AND 5),
    my_thesis          TEXT        NOT NULL,
    my_thesis_breaker  TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_ticker
    ON decision (market, ticker, decided_at DESC);


-- ------------------------------------------------------------
-- decision_evidence: 결정의 근거로 연결한 하이라이트 그룹
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_evidence (
    decision_id         UUID NOT NULL REFERENCES decision (id) ON DELETE CASCADE,
    highlight_group_id  UUID NOT NULL REFERENCES highlight_group (id) ON DELETE CASCADE,
    PRIMARY KEY (decision_id, highlight_group_id)
);

-- 근거 하이라이트는 결정이 참고한 리포트의 것이어야 함
CREATE OR REPLACE FUNCTION check_evidence_report() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM decision d
        JOIN highlight_group g ON g.report_id = d.report_id
        WHERE d.id = NEW.decision_id AND g.id = NEW.highlight_group_id
    ) THEN
        RAISE EXCEPTION '근거 하이라이트가 결정이 참고한 리포트에 속하지 않습니다.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evidence_report ON decision_evidence;
CREATE TRIGGER trg_evidence_report
    BEFORE INSERT OR UPDATE ON decision_evidence
    FOR EACH ROW EXECUTE FUNCTION check_evidence_report();
