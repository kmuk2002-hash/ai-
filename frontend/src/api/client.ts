/**
 * 백엔드 API 클라이언트.
 * VITE_USE_MOCK=true 이면 목업(src/mocks)으로, 아니면 /api/* 로 요청한다.
 * /api 는 vite.config.ts의 프록시가 http://localhost:8000 으로 넘긴다.
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
import { mockApi } from '../mocks/server'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* 본문이 JSON이 아님 */
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v) as [string, string][]
  return entries.length ? '?' + new URLSearchParams(entries).toString() : ''
}

/**
 * POST /analyze/stream: 노드가 끝날 때마다 onEvent를 부르고, 저장된 리포트로 끝난다.
 * 응답 형식(SSE): "event: 이름\ndata: JSON\n\n" 이 반복된다.
 */
async function analyzeStream(req: AnalyzeRequest, onEvent: (e: AnalyzeEvent) => void): Promise<StoredReport> {
  const res = await fetch(BASE + '/analyze/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(req),
  })
  if (!res.ok || !res.body) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* 본문이 JSON이 아님 */
    }
    throw new Error(detail)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let cut: number
    while ((cut = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, cut)
      buf = buf.slice(cut + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      const payload = JSON.parse(data)
      if (event === 'report') return payload as StoredReport
      if (event === 'error') throw new Error(payload.detail ?? '분석 중 오류')
      onEvent({ type: event, ...payload } as AnalyzeEvent)
    }
  }
  throw new Error('분석이 끝나기 전에 연결이 끊겼어요.')
}

const realApi = {
  analyze: (req: AnalyzeRequest) =>
    request<StoredReport>('/analyze', { method: 'POST', body: JSON.stringify(req) }),

  analyzeStream,

  getReport: (id: string) => request<StoredReport>(`/reports/${encodeURIComponent(id)}`),

  listReports: (params: { ticker?: string; market?: Market } = {}) =>
    request<ReportListItem[]>('/reports' + qs(params)),

  listHighlights: (reportId: string) =>
    request<HighlightGroup[]>(`/reports/${encodeURIComponent(reportId)}/highlights`),

  createHighlight: (reportId: string, body: HighlightCreate) =>
    request<HighlightGroup>(`/reports/${encodeURIComponent(reportId)}/highlights`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  createDecision: (body: DecisionCreate) =>
    request<StoredDecision>('/decisions', { method: 'POST', body: JSON.stringify(body) }),

  listAllDecisions: () => request<StoredDecision[]>('/decisions'),

  listNotifications: () => request<DecisionNotice[]>('/notifications'),

  listDecisions: (ticker: string, market: Market) =>
    request<StoredDecision[]>(`/decisions/${encodeURIComponent(ticker)}` + qs({ market })),
}

export const api: typeof realApi = USE_MOCK ? mockApi : realApi
