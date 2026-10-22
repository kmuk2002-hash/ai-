/**
 * backend/agent/schemas.py 의 Pydantic 모델과 1:1로 대응하는 타입.
 * 날짜(date)는 "YYYY-MM-DD", 일시(datetime)는 ISO 8601 문자열로 주고받는다.
 */

// ─────────────────────────────────────────────
// 공통 타입
// ─────────────────────────────────────────────

export type Market = 'US' | 'KR'

/** support 🟢근거 / concern 🔴우려 / to_verify 🟡확인 필요 / disagree ⚪반대 */
export type HighlightTag = 'support' | 'concern' | 'to_verify' | 'disagree'

export type ReportField =
  | 'investment_thesis'
  | 'risks'
  | 'consensus_gap'
  | 'thesis_breakers'
  | 'past_decision_review'

export type DecisionAction = 'buy' | 'hold' | 'sell'

export interface Source {
  title: string
  url: string | null
  doc_type: '10-K' | '10-Q' | 'broker_report' | 'web' | 'quant_api'
  section: string | null
}

// ─────────────────────────────────────────────
// 퀀트 스냅샷
// ─────────────────────────────────────────────

export interface QuantSnapshot {
  ticker: string
  market: Market
  as_of_date: string
  currency: string

  sector: string | null
  industry: string | null
  market_cap: number | null

  price: number | null
  change_pct: number | null
  volume: number | null

  per: number | null
  forward_per: number | null
  pbr: number | null
  roe: number | null
  roa: number | null
  profit_margin: number | null
  dividend_yield: number | null

  ma_50: number | null
  ma_200: number | null
  volatility_60d: number | null
  return_6m: number | null
  return_12m: number | null

  analyst_target_price: number | null
  eps_estimate: number | null
  eps_actual: number | null
  eps_surprise_pct: number | null
}

// ─────────────────────────────────────────────
// 리포트
// ─────────────────────────────────────────────

export interface ReportDraft {
  investment_thesis: string
  risks: string
  consensus_gap: string
  thesis_breakers: string
  sources: Source[]
}

export type CheckCategory = 'data_change' | 'thesis_breaker' | 'to_verify' | 'thesis_validity'
export type CheckStatus = 'triggered' | 'not_triggered' | 'insufficient_evidence'

export interface PastDecisionCheck {
  category: CheckCategory
  target: string
  status: CheckStatus
  evidence: string
  sources: Source[]
}

export interface PastDecisionReview {
  summary: string
  checks: PastDecisionCheck[]
}

export interface Report extends ReportDraft {
  ticker: string
  market: Market
  as_of_date: string
  quant_snapshot: QuantSnapshot
  past_decision_review: PastDecisionReview | null
}

/** API 응답: DB에 저장된 리포트 (id 포함) */
export interface StoredReport extends Report {
  id: string
  created_at?: string
}

export interface ReportListItem {
  id: string
  ticker: string
  market: Market
  as_of_date: string
  created_at?: string
}

// ─────────────────────────────────────────────
// 하이라이트
// ─────────────────────────────────────────────

export interface HighlightSpan {
  field: ReportField
  start_offset: number
  end_offset: number
  quoted_text: string
}

export interface HighlightGroup {
  id: string | null
  tag: HighlightTag
  comment: string | null
  spans: HighlightSpan[]
  created_at: string | null
}

/** POST /reports/{id}/highlights 요청 본문 */
export interface HighlightCreate {
  tag: HighlightTag
  comment: string | null
  spans: HighlightSpan[]
}

// ─────────────────────────────────────────────
// 결정
// ─────────────────────────────────────────────

export interface Decision {
  ticker: string
  market: Market
  decided_at: string
  action: DecisionAction
  weight: number | null
  confidence: number
  my_thesis: string
  my_thesis_breaker: string
}

/** POST /decisions 요청 본문 (decided_at은 서버가 채움) */
export interface DecisionCreate extends Omit<Decision, 'decided_at'> {
  report_id: string
  evidence_group_ids: string[]
}

/** GET /decisions/{ticker} 응답 항목 */
export interface StoredDecision extends Decision {
  id: string
  report_id: string
  evidence_group_ids: string[]
}

/**
 * GET /notifications 항목: 결정을 내린 뒤 같은 종목을 다시 분석했을 때 생기는 소식.
 * 새 리포트의 '과거 결정 대비' 점검 결과를, 그 결정을 내린 원래 리포트에 붙여 보여준다.
 */
export interface DecisionNotice {
  /** 새 리포트 id (알림 id로도 씀) */
  id: string
  ticker: string
  market: Market
  /** 원래 결정 */
  decision_id: string
  decision_report_id: string
  action: DecisionAction
  decided_at: string
  /** 새 리포트 */
  report_id: string
  as_of_date: string
  created_at: string
  summary: string
  /** 판정이 '충족'인 점검 항목 */
  triggered: PastDecisionCheck[]
  /** 철회 조건이 충족되면 alert, 아니면 info */
  level: 'alert' | 'info'
}

/** POST /analyze 요청 본문 */
export interface AnalyzeRequest {
  ticker: string
  market: Market
  as_of_date: string
}

/** POST /analyze/stream 진행 이벤트 (SSE) */
export type AnalyzeEvent =
  /** 메인 그래프 노드 하나가 끝남. past_decision일 때는 has_past가 함께 온다 */
  | { type: 'node'; node: string; elapsed: number; has_past?: boolean }
  /** 서브그래프(펀더멘털) 안 단계 하나가 끝남 */
  | { type: 'step'; node: string; step: string; elapsed: number }

// ─────────────────────────────────────────────
// 화면 표시용 라벨
// ─────────────────────────────────────────────

export const TAG_META: Record<HighlightTag, { label: string; emoji: string }> = {
  support: { label: '근거', emoji: '🟢' },
  concern: { label: '우려', emoji: '🔴' },
  to_verify: { label: '확인 필요', emoji: '🟡' },
  disagree: { label: '반대', emoji: '⚪' },
}

export const FIELD_LABEL: Record<ReportField, string> = {
  investment_thesis: '투자 논리',
  risks: '리스크',
  consensus_gap: '컨센서스 대비 차이',
  thesis_breakers: '철회 조건',
  past_decision_review: '과거 결정 대비',
}

export const ACTION_LABEL: Record<DecisionAction, string> = {
  buy: '매수',
  hold: '보류',
  sell: '매도',
}

export const STATUS_LABEL: Record<CheckStatus, string> = {
  triggered: '해당함',
  not_triggered: '해당하지 않음',
  insufficient_evidence: '판단 근거 부족',
}

export const CATEGORY_LABEL: Record<CheckCategory, string> = {
  data_change: '데이터 변화',
  thesis_breaker: '철회 조건',
  to_verify: '확인 필요 항목',
  thesis_validity: '매수 근거 유효성',
}
