<script setup lang="ts">
/**
 * 퀀트 스냅샷 데이터 띠.
 * 장부의 숫자 칸처럼 세로 괘선으로 나눈 한 줄. 값이 없으면 "데이터 없음"을 흐리게.
 */
import { computed } from 'vue'
import type { QuantSnapshot } from '../types'

const props = defineProps<{ q: QuantSnapshot }>()

const NA = '데이터 없음'

type Trend = 'up' | 'down' | null

interface Cell {
  label: string
  value: string
  sub?: string
  trend?: Trend
  subTrend?: Trend
  wide?: boolean
}

const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && !Number.isNaN(v)

function fmt(v: number | null, digits = 1): string {
  if (!isNum(v)) return NA
  return v.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}
function pct(v: number | null, digits = 1): string {
  if (!isNum(v)) return NA
  return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: digits }) + '%'
}
const trend = (v: number | null): Trend => (!isNum(v) || v === 0 ? null : v > 0 ? 'up' : 'down')

function bigMoney(v: number | null): string {
  if (!isNum(v)) return NA
  const units: [number, string][] = [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']]
  for (const [u, s] of units) if (Math.abs(v) >= u) return `${(v / u).toFixed(2)}${s}`
  return fmt(v, 0)
}

const upside = computed<number | null>(() => {
  const { price, analyst_target_price: t } = props.q
  return isNum(price) && isNum(t) && price !== 0 ? ((t - price) / price) * 100 : null
})

const cells = computed<Cell[]>(() => {
  const q = props.q
  return [
    { label: `현재가 (${q.currency})`, value: fmt(q.price, 2), sub: pct(q.change_pct), subTrend: trend(q.change_pct), wide: true },
    {
      label: '목표주가',
      value: fmt(q.analyst_target_price, 2),
      sub: isNum(upside.value) ? `여력 ${pct(upside.value)}` : undefined,
      subTrend: trend(upside.value),
    },
    { label: 'PER', value: fmt(q.per) },
    { label: 'Forward PER', value: fmt(q.forward_per) },
    { label: 'EPS 서프라이즈', value: pct(q.eps_surprise_pct), trend: trend(q.eps_surprise_pct), sub: isNum(q.eps_estimate) && isNum(q.eps_actual) ? `${q.eps_estimate.toFixed(2)} → ${q.eps_actual.toFixed(2)}` : undefined },
    { label: '6개월', value: pct(q.return_6m), trend: trend(q.return_6m) },
    { label: '12개월', value: pct(q.return_12m), trend: trend(q.return_12m) },
    { label: 'PBR', value: fmt(q.pbr) },
    { label: 'ROE', value: isNum(q.roe) ? `${fmt(q.roe)}%` : NA },
    { label: '시가총액', value: bigMoney(q.market_cap) },
  ]
})
</script>

<template>
  <div class="quant" role="list" aria-label="퀀트 지표">
    <div v-for="c in cells" :key="c.label" :class="['cell', { wide: c.wide }]" role="listitem">
      <span class="label">{{ c.label }}</span>
      <span :class="['value', c.value === NA ? 'na' : 'num', c.trend]">{{ c.value }}</span>
      <span v-if="c.sub" :class="['sub', 'num', c.subTrend]">{{ c.sub }}</span>
    </div>
  </div>
</template>

<style scoped>
.quant {
  display: grid;
  grid-template-columns: minmax(150px, 1.4fr) repeat(9, minmax(0, 1fr));
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--rule-strong);
}
.cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 10px 12px 12px;
  border-left: 1px solid var(--rule);
}
.cell:first-child {
  border-left: none;
  padding-left: 0;
}
.label {
  font-size: var(--t-xs);
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.value {
  font-size: 17px;
  font-weight: 500;
  line-height: 1.3;
  white-space: nowrap;
}
.wide .value {
  font-size: 26px;
  font-weight: 500;
}
.value.na {
  font-family: var(--font-sans);
  font-size: var(--t-sm);
  font-weight: 400;
  line-height: 1.75;
  color: var(--ink-faint);
}
.sub {
  font-size: var(--t-xs);
  color: var(--ink-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.up {
  color: var(--up);
}
.down {
  color: var(--down);
}

@media (max-width: 1100px) {
  .quant {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
  .cell.wide {
    grid-column: span 1;
  }
  .cell:nth-child(5n + 1) {
    border-left: none;
    padding-left: 0;
  }
  .cell:nth-child(n + 6) {
    border-top: 1px solid var(--rule);
  }
}
@media (max-width: 600px) {
  .quant {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .cell.wide {
    grid-column: 1 / -1;
  }
  .cell:nth-child(5n + 1) {
    border-left: 1px solid var(--rule);
    padding-left: 12px;
  }
  .cell:nth-child(n + 6) {
    border-top: none;
  }
  .cell {
    border-top: 1px solid var(--rule);
  }
  .cell.wide {
    border-top: none;
    border-left: none;
    padding-left: 0;
  }
  .cell:nth-child(2n) {
    border-left: none;
    padding-left: 0;
  }
}
</style>
