/**
 * 알림 계산 규칙 (서버 GET /notifications와 같은 규칙). 목업 서버도 이 함수를 쓴다.
 */
import type { DecisionNotice, StoredDecision, StoredReport } from '../types'

/** 새 리포트(과거 결정 대비 포함) + 그때 비교한 결정 → 알림 */
export function toNotice(r: StoredReport, d: StoredDecision): DecisionNotice | null {
  const review = r.past_decision_review
  if (!review) return null
  const triggered = review.checks.filter((c) => c.status === 'triggered')
  return {
    id: r.id,
    ticker: r.ticker,
    market: r.market,
    decision_id: d.id,
    decision_report_id: d.report_id,
    action: d.action,
    decided_at: d.decided_at,
    report_id: r.id,
    as_of_date: r.as_of_date,
    created_at: r.created_at ?? new Date().toISOString(),
    summary: review.summary,
    triggered,
    level: triggered.some((c) => c.category === 'thesis_breaker') ? 'alert' : 'info',
  }
}
