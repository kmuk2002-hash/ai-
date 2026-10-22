/**
 * 목업 리포트 생성기. 백엔드 없이 화면을 개발·시연하기 위한 가짜 데이터.
 * 모든 문장 앞에 "(목업)"을 붙여 실제 분석 결과와 구분한다.
 */
import type {
  Market,
  PastDecisionReview,
  QuantSnapshot,
  Report,
  StoredDecision,
} from '../types'

function emptySnapshot(ticker: string, market: Market, asOf: string): QuantSnapshot {
  return {
    ticker,
    market,
    as_of_date: asOf,
    currency: market === 'US' ? 'USD' : 'KRW',
    sector: null,
    industry: null,
    market_cap: null,
    price: null,
    change_pct: null,
    volume: null,
    per: null,
    forward_per: null,
    pbr: null,
    roe: null,
    roa: null,
    profit_margin: null,
    dividend_yield: null,
    ma_50: null,
    ma_200: null,
    volatility_60d: null,
    return_6m: null,
    return_12m: null,
    analyst_target_price: null,
    eps_estimate: null,
    eps_actual: null,
    eps_surprise_pct: null,
  }
}

/** 종목별 목업 퀀트 값. 없는 종목은 일부 값만 채운 기본값 사용 */
const QUANT_PRESETS: Record<string, Partial<QuantSnapshot>> = {
  NVDA: {
    sector: 'Technology',
    industry: 'Semiconductors',
    market_cap: 4.1e12,
    price: 168.4,
    change_pct: -2.1,
    volume: 210_000_000,
    per: 52.3,
    forward_per: 34.8,
    pbr: 44.0,
    roe: 105.0,
    roa: 70.0,
    profit_margin: 52.0,
    dividend_yield: 0.02,
    ma_50: 172.0,
    ma_200: 150.5,
    volatility_60d: 41.0,
    return_6m: 18.2,
    return_12m: 32.5,
    analyst_target_price: 205.0,
    eps_estimate: 1.02,
    eps_actual: 1.05,
    eps_surprise_pct: 2.94,
  },
  AAPL: {
    sector: 'Technology',
    industry: 'Consumer Electronics',
    market_cap: 3.4e12,
    price: 230.0,
    change_pct: 1.2,
    volume: 52_000_000,
    per: 31.5,
    forward_per: 28.0,
    pbr: 45.0,
    roe: 150.0,
    roa: 28.0,
    profit_margin: 24.0,
    dividend_yield: null,
    ma_50: 225.0,
    ma_200: 210.0,
    volatility_60d: 22.0,
    return_6m: 8.5,
    return_12m: 15.0,
    analyst_target_price: null,
    eps_estimate: 1.6,
    eps_actual: 1.65,
    eps_surprise_pct: 3.125,
  },
}

export function buildQuant(ticker: string, market: Market, asOf: string): QuantSnapshot {
  const preset = QUANT_PRESETS[ticker] ?? {
    price: 100.0,
    change_pct: 0.4,
    per: 18.0,
    forward_per: 16.5,
    pbr: 2.1,
    roe: 12.0,
    return_6m: 3.0,
  }
  return { ...emptySnapshot(ticker, market, asOf), ...preset }
}

export function buildReport(
  ticker: string,
  market: Market,
  asOf: string,
  latest: StoredDecision | null,
): Report {
  const q = buildQuant(ticker, market, asOf)
  return {
    ticker,
    market,
    as_of_date: asOf,
    quant_snapshot: q,
    investment_thesis:
      `(목업) ${ticker}는 핵심 사업의 점유율을 유지하면서 신규 제품군으로 매출원을 넓히고 있다.\n` +
      `경영진은 MD&A에서 다음 회계연도에도 두 자릿수 매출 성장을 예상한다고 밝혔다.\n` +
      `서비스·소프트웨어 매출 비중이 높아지면서 이익률이 구조적으로 개선되는 흐름이다.`,
    risks:
      `(목업) 주요 고객사 몇 곳에 매출이 집중되어 있어, 이들의 투자 축소가 실적에 직접 영향을 준다.\n` +
      `수출 규제가 강화되면 일부 지역 매출이 줄어들 수 있다고 10-K Item 1A에서 밝히고 있다.\n` +
      `공급망 차질로 인한 마진 압박 가능성이 남아 있다.`,
    consensus_gap:
      `(목업) 직전 분기 EPS는 예상치를 소폭 상회했지만, 시장은 이미 높은 성장을 주가에 반영하고 있다.\n` +
      `Forward PER이 현재 PER보다 낮아 이익 성장은 기대되지만, 가이던스가 기대에 못 미치면 주가 변동성이 커질 수 있다.`,
    thesis_breakers:
      `(목업) 데이터센터 매출 성장률이 2개 분기 연속 20% 미만으로 떨어지는 경우.\n` +
      `영업이익률이 직전 4개 분기 평균보다 5%p 이상 하락하는 경우.`,
    sources: [
      { title: `${ticker} 10-K (FY2025)`, url: null, doc_type: '10-K', section: 'Item 1A' },
      { title: `${ticker} 10-K (FY2025)`, url: null, doc_type: '10-K', section: 'Item 7' },
      { title: 'Alpha Vantage OVERVIEW / EARNINGS', url: 'https://www.alphavantage.co/documentation/', doc_type: 'quant_api', section: null },
      { title: '(목업) 최근 실적 관련 기사', url: 'https://example.com/news', doc_type: 'web', section: null },
    ],
    past_decision_review: latest ? buildReview(latest) : null,
  }
}

function buildReview(latest: StoredDecision): PastDecisionReview {
  const d = latest.decided_at.slice(0, 10)
  return {
    summary:
      `(목업) ${d}의 결정(${latest.action === 'buy' ? '매수' : latest.action === 'hold' ? '보류' : '매도'}) 이후 주가와 이익 전망이 함께 올랐다.\n` +
      `내가 정한 철회 조건은 아직 충족되지 않았지만, 확인이 필요하다고 표시한 마진 이슈는 이번 분기에 일부 현실화되었다.`,
    checks: [
      {
        category: 'thesis_breaker',
        target: latest.my_thesis_breaker,
        status: 'not_triggered',
        evidence: '(목업) 최근 분기 데이터센터 매출 성장률은 20%를 상회했다.',
        sources: [],
      },
      {
        category: 'to_verify',
        target: '공급망 차질로 인한 마진 압박 가능성',
        status: 'triggered',
        evidence: '(목업) 직전 분기 매출총이익률이 전 분기 대비 하락했다.',
        sources: [],
      },
      {
        category: 'thesis_validity',
        target: latest.my_thesis,
        status: 'insufficient_evidence',
        evidence: '(목업) 신규 제품군 매출이 별도로 공시되지 않아 판단할 근거가 부족하다.',
        sources: [],
      },
      {
        category: 'data_change',
        target: 'PER, 목표주가',
        status: 'not_triggered',
        evidence: '(목업) PER은 하락했고 애널리스트 목표주가는 상향되었다.',
        sources: [],
      },
    ],
  }
}
