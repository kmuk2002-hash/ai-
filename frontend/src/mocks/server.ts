/**
 * 목업 백엔드. 실제 API와 같은 함수 시그니처로 동작하며,
 * 데이터는 메모리에 두고 localStorage에도 저장해 새로고침 후에도 유지한다.
 */
import type {
  AnalyzeEvent,
  DecisionNotice,
  AnalyzeRequest,
  DecisionCreate,
  HighlightCreate,
  HighlightGroup,
  Market,
  ReportListItem,
  StoredDecision,
  StoredReport,
} from '../types'
import { buildReport } from './fixtures'
import { toNotice } from '../lib/notice'

interface MockDB {
  reports: StoredReport[]
  highlights: Record<string, HighlightGroup[]>
  decisions: (StoredDecision & { id: string })[]
}

const STORAGE_KEY = 'invest-mock-db-v2'
const ANALYZE_DELAY_MS = 2500

function uid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function seed(): MockDB {
  // NVDA: 과거 결정이 이미 있는 종목 → 분석하면 "과거 결정 대비" 섹션이 나타남
  // AAPL 등 다른 종목: 처음 분석하는 종목 → 과거 결정 대비 섹션 없음
  const pastReport: StoredReport = {
    id: 'seed-report-nvda',
    created_at: '2026-07-20T09:00:00+09:00',
    ...buildReport('NVDA', 'US', '2026-07-20', null),
  }
  const groupId = 'seed-group-nvda'
  const quoted = '공급망 차질로 인한 마진 압박 가능성'
  const start = pastReport.risks.indexOf(quoted)
  const nvdaDecision: StoredDecision = {
    id: 'seed-decision-nvda',
    report_id: pastReport.id,
    ticker: 'NVDA',
    market: 'US',
    decided_at: '2026-07-21T10:00:00+09:00',
    action: 'buy',
    weight: 0.1,
    confidence: 4,
    my_thesis: '(목업) 데이터센터 수요가 2년 이상 이어질 것으로 본다',
    my_thesis_breaker: '데이터센터 매출 성장률이 2개 분기 연속 20% 미만',
    evidence_group_ids: [groupId],
  }
  // NVDA를 석 달 뒤 다시 분석 → 확인 필요 항목이 현실화됨 (알림: 정보)
  const nvdaFollow: StoredReport = {
    id: 'seed-report-nvda-2',
    created_at: '2026-10-15T09:10:00+09:00',
    ...buildReport('NVDA', 'US', '2026-10-15', nvdaDecision),
  }

  // AAPL: 보류 결정 → 다시 분석했더니 철회 조건 충족 (알림: 경고)
  const aaplReport: StoredReport = {
    id: 'seed-report-aapl',
    created_at: '2026-08-12T21:30:00+09:00',
    ...buildReport('AAPL', 'US', '2026-08-12', null),
  }
  const aaplDecision: StoredDecision = {
    id: 'seed-decision-aapl',
    report_id: aaplReport.id,
    ticker: 'AAPL',
    market: 'US',
    decided_at: '2026-08-12T22:05:00+09:00',
    action: 'hold',
    weight: 0.05,
    confidence: 3,
    my_thesis: '(목업) 서비스 매출 비중 확대로 이익률이 버텨 줄 것',
    my_thesis_breaker: '서비스 부문 매출 성장률이 한 자릿수로 떨어지는 경우',
    evidence_group_ids: [],
  }
  const aaplFollow: StoredReport = {
    id: 'seed-report-aapl-2',
    created_at: '2026-10-08T08:40:00+09:00',
    ...buildReport('AAPL', 'US', '2026-10-08', aaplDecision),
  }
  const breaker = aaplFollow.past_decision_review!.checks[0]
  breaker.status = 'triggered'
  breaker.evidence = '(목업) 직전 분기 서비스 부문 매출 성장률이 8.4%로 한 자릿수에 들어섰다.'
  aaplFollow.past_decision_review!.summary =
    '(목업) 2026-08-12의 결정(보류) 이후 서비스 부문 성장률이 둔화했다.\n내가 정한 철회 조건이 충족되었으므로 보유 논리를 다시 점검해야 한다.'

  // MSFT: 리포트만 읽고 아직 결정하지 않음
  const msftReport: StoredReport = {
    id: 'seed-report-msft',
    created_at: '2026-09-30T19:20:00+09:00',
    ...buildReport('MSFT', 'US', '2026-09-30', null),
  }

  return {
    reports: [pastReport, aaplReport, msftReport, aaplFollow, nvdaFollow],
    highlights: {
      [pastReport.id]: [
        {
          id: groupId,
          tag: 'to_verify',
          comment: '(목업) 다음 분기 매출총이익률 확인',
          spans: [{ field: 'risks', start_offset: start, end_offset: start + quoted.length, quoted_text: quoted }],
          created_at: '2026-07-20T10:00:00+09:00',
        },
      ],
    },
    decisions: [nvdaDecision, aaplDecision],
  }
}

function load(): MockDB {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as MockDB
  } catch {
    /* 저장소를 쓸 수 없으면 메모리만 사용 */
  }
  return seed()
}

const db: MockDB = load()

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db))
  } catch {
    /* 무시 */
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T

function latestDecision(ticker: string, market: Market): StoredDecision | null {
  const list = db.decisions
    .filter((d) => d.ticker === ticker && d.market === market)
    .sort((a, b) => b.decided_at.localeCompare(a.decided_at))
  return list[0] ?? null
}

export const mockApi = {
  async analyze(req: AnalyzeRequest): Promise<StoredReport> {
    await sleep(ANALYZE_DELAY_MS)
    const ticker = req.ticker.trim().toUpperCase()
    const report: StoredReport = {
      id: uid(),
      created_at: new Date().toISOString(),
      ...buildReport(ticker, req.market, req.as_of_date, latestDecision(ticker, req.market)),
    }
    db.reports.push(report)
    persist()
    return clone(report)
  },

  async analyzeStream(req: AnalyzeRequest, onEvent: (e: AnalyzeEvent) => void): Promise<StoredReport> {
    const ticker = req.ticker.trim().toUpperCase()
    const past = latestDecision(ticker, req.market)
    const t0 = Date.now()
    const at = () => Math.round((Date.now() - t0) / 100) / 10
    const node = (n: string, extra: Partial<AnalyzeEvent> = {}) => onEvent({ type: 'node', node: n, elapsed: at(), ...extra } as AnalyzeEvent)
    const step = (s: string) => onEvent({ type: 'step', node: 'fundamental', step: s, elapsed: at() })

    await sleep(150)
    node('past_decision', { has_past: past !== null })
    await sleep(350)
    step('search_documents')
    await sleep(250)
    step('search_web')
    step('unify_documents')
    await sleep(200)
    node('quant')
    await sleep(350)
    step('relevance_check')
    await sleep(450)
    step('fundamental_summary')
    node('fundamental')
    await sleep(500)
    node('write_report')
    node('old_exist')
    if (past) {
      await sleep(400)
      node('new_vs_old')
    }
    const report: StoredReport = {
      id: uid(),
      created_at: new Date().toISOString(),
      ...buildReport(ticker, req.market, req.as_of_date, past),
    }
    db.reports.push(report)
    persist()
    return clone(report)
  },

  async getReport(id: string): Promise<StoredReport> {
    await sleep(150)
    const r = db.reports.find((x) => x.id === id)
    if (!r) throw new Error('리포트를 찾을 수 없습니다.')
    return clone(r)
  },

  async listReports(params: { ticker?: string; market?: Market } = {}): Promise<ReportListItem[]> {
    await sleep(100)
    return db.reports
      .filter((r) => (!params.ticker || r.ticker === params.ticker) && (!params.market || r.market === params.market))
      .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
      .map(({ id, ticker, market, as_of_date, created_at }) => ({ id, ticker, market, as_of_date, created_at }))
  },

  async listHighlights(reportId: string): Promise<HighlightGroup[]> {
    await sleep(100)
    return clone(db.highlights[reportId] ?? [])
  },

  async createHighlight(reportId: string, body: HighlightCreate): Promise<HighlightGroup> {
    await sleep(150)
    const group: HighlightGroup = { id: uid(), created_at: new Date().toISOString(), ...clone(body) }
    ;(db.highlights[reportId] ??= []).push(group)
    persist()
    return clone(group)
  },

  async createDecision(body: DecisionCreate): Promise<StoredDecision> {
    await sleep(150)
    const decision: StoredDecision = { id: uid(), decided_at: new Date().toISOString(), ...clone(body) }
    db.decisions.push(decision)
    persist()
    return clone(decision)
  },

  async listDecisions(ticker: string, market: Market): Promise<StoredDecision[]> {
    await sleep(100)
    return clone(
      db.decisions
        .filter((d) => d.ticker === ticker && d.market === market)
        .sort((a, b) => b.decided_at.localeCompare(a.decided_at)),
    )
  },

  async listAllDecisions(): Promise<StoredDecision[]> {
    await sleep(100)
    return clone([...db.decisions].sort((a, b) => b.decided_at.localeCompare(a.decided_at)))
  },

  /** 리포트마다, 그 리포트 작성 직전의 최신 결정과 비교한 점검 결과 → 알림 */
  async listNotifications(): Promise<DecisionNotice[]> {
    await sleep(80)
    const out: DecisionNotice[] = []
    for (const r of db.reports) {
      if (!r.past_decision_review || !r.created_at) continue
      const d = db.decisions
        .filter((x) => x.ticker === r.ticker && x.market === r.market && Date.parse(x.decided_at) < Date.parse(r.created_at!))
        .sort((a, b) => b.decided_at.localeCompare(a.decided_at))[0]
      const n = d ? toNotice(r, d) : null
      if (n) out.push(n)
    }
    return out.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
  },

  /** 개발용: 목업 데이터를 초기 상태로 되돌림 */
  reset() {
    const fresh = seed()
    db.reports = fresh.reports
    db.highlights = fresh.highlights
    db.decisions = fresh.decisions
    persist()
  },
}
