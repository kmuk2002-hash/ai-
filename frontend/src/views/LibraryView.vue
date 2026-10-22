<script setup lang="ts">
/**
 * 기록 보관함: 지금까지 만든 리포트와 그 리포트로 내린 결정을 날짜별·종목별로 모아 본다.
 * 결정 이후 다시 분석해서 생긴 소식(알림)이 있으면 원래 리포트 옆에 표시한다.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import type { ReportListItem, StoredDecision } from '../types'
import { ACTION_LABEL } from '../types'
import { useNotices } from '../composables/notices'
import { dayKey, dayLabel, shortDate } from '../lib/format'

type GroupBy = 'date' | 'ticker'

const VIEW_KEY = 'invest-library-view'
function savedView(): GroupBy {
  try {
    return localStorage.getItem(VIEW_KEY) === 'ticker' ? 'ticker' : 'date'
  } catch {
    return 'date'
  }
}

const groupBy = ref<GroupBy>(savedView())
watch(groupBy, (v) => {
  try {
    localStorage.setItem(VIEW_KEY, v)
  } catch {
    /* 기억 못 해도 동작 */
  }
})

const query = ref('')
const onlyNews = ref(false)
const reports = ref<ReportListItem[]>([])
const decisions = ref<StoredDecision[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const { forReport, isRead, unread } = useNotices()

onMounted(async () => {
  try {
    const [r, d] = await Promise.all([api.listReports(), api.listAllDecisions()])
    reports.value = r
    decisions.value = d
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})

/** 리포트 id → 그 리포트를 보고 내린 결정 (여러 개면 최신) */
const decisionOf = computed(() => {
  const m = new Map<string, StoredDecision>()
  for (const d of decisions.value) {
    const prev = m.get(d.report_id)
    if (!prev || Date.parse(d.decided_at) > Date.parse(prev.decided_at)) m.set(d.report_id, d)
  }
  return m
})

interface Row {
  r: ReportListItem
  decision: StoredDecision | null
  news: number
  alert: boolean
}

const rows = computed<Row[]>(() => {
  const q = query.value.trim().toUpperCase()
  return reports.value
    .filter((r) => !q || r.ticker.includes(q))
    .map((r) => {
      const ns = forReport(r.id).filter((n) => !isRead(n.id))
      return { r, decision: decisionOf.value.get(r.id) ?? null, news: ns.length, alert: ns.some((n) => n.level === 'alert') }
    })
    .filter((row) => !onlyNews.value || row.news > 0)
    .sort((a, b) => Date.parse(b.r.created_at ?? '') - Date.parse(a.r.created_at ?? ''))
})

interface Group {
  key: string
  title: string
  sub: string
  latest: StoredDecision | null
  ticker?: { ticker: string; market: string }
  rows: Row[]
}

const groups = computed<Group[]>(() => {
  const map = new Map<string, Row[]>()
  for (const row of rows.value) {
    const key = groupBy.value === 'date' ? dayKey(row.r.created_at ?? row.r.as_of_date) : `${row.r.market}:${row.r.ticker}`
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(row)
  }
  const out: Group[] = []
  for (const [key, rs] of map) {
    const decided = rs.filter((x) => x.decision)
    if (groupBy.value === 'date') {
      out.push({ key, title: dayLabel(key), sub: `리포트 ${rs.length}개, 결정 ${decided.length}개`, latest: null, rows: rs })
    } else {
      const [market, ticker] = key.split(':')
      const latest = decisions.value.find((d) => d.ticker === ticker && d.market === market) ?? null
      out.push({ key, title: ticker, sub: `리포트 ${rs.length}개, 결정 ${decided.length}개`, latest, ticker: { ticker, market }, rows: rs })
    }
  }
  return out
})

const totals = computed(() => ({
  reports: reports.value.length,
  decisions: decisions.value.length,
  tickers: new Set(reports.value.map((r) => r.ticker)).size,
}))
</script>

<template>
  <div class="page library">
    <header class="head">
      <div>
        <h1>기록 보관함</h1>
        <p class="lead">
          리포트 <b class="num">{{ totals.reports }}</b>개, 결정 <b class="num">{{ totals.decisions }}</b>개,
          종목 <b class="num">{{ totals.tickers }}</b>개<template v-if="unread.length">,
            읽지 않은 소식 <b class="num news-count">{{ unread.length }}</b>건</template>
        </p>
      </div>
      <div class="controls">
        <div class="seg" role="radiogroup" aria-label="묶는 기준">
          <button type="button" role="radio" :aria-checked="groupBy === 'date'" @click="groupBy = 'date'">날짜별</button>
          <button type="button" role="radio" :aria-checked="groupBy === 'ticker'" @click="groupBy = 'ticker'">종목별</button>
        </div>
        <label class="search">
          <span class="sr-only">티커로 찾기</span>
          <input v-model="query" placeholder="티커로 찾기" autocomplete="off" spellcheck="false" />
        </label>
        <label class="only">
          <input v-model="onlyNews" type="checkbox" />
          새 소식만
        </label>
      </div>
    </header>

    <div v-if="loading" class="state">불러오는 중…</div>
    <div v-else-if="error" class="state error" role="alert">
      목록을 불러오지 못했어요. {{ error }}
    </div>
    <div v-else-if="!rows.length" class="state">
      <template v-if="query || onlyNews">조건에 맞는 리포트가 없어요. 검색어나 필터를 바꿔 보세요.</template>
      <template v-else>
        아직 만든 리포트가 없어요.
        <RouterLink to="/">첫 종목을 분석해 보세요</RouterLink>
      </template>
    </div>

    <section v-for="g in groups" v-else :key="g.key" class="group" :aria-labelledby="`g-${g.key}`">
      <div class="g-head">
        <h2 :id="`g-${g.key}`" :class="{ num: groupBy === 'ticker' }">{{ g.title }}</h2>
        <span class="g-sub">{{ g.sub }}</span>
        <span v-if="g.latest" :class="['chip', g.latest.action]">최근 결정 {{ ACTION_LABEL[g.latest.action] }}</span>
        <RouterLink
          v-if="g.ticker"
          class="g-link"
          :to="{ name: 'history', params: { market: g.ticker.market, ticker: g.ticker.ticker } }"
        >
          결정 이력
        </RouterLink>
      </div>

      <ul class="rows">
        <li v-for="row in g.rows" :key="row.r.id">
          <RouterLink class="row" :to="{ name: 'report', params: { id: row.r.id }, hash: row.news ? '#since' : '' }">
            <span v-if="groupBy === 'date'" class="r-ticker num">{{ row.r.ticker }}</span>
            <span v-else class="r-made">{{ shortDate(row.r.created_at ?? row.r.as_of_date) }} 작성</span>
            <span class="r-asof">기준일 <span class="num">{{ row.r.as_of_date }}</span></span>
            <span class="r-decision">
              <template v-if="row.decision">
                <span :class="['chip', row.decision.action]">{{ ACTION_LABEL[row.decision.action] }}</span>
                <span class="conf" :aria-label="`확신 ${row.decision.confidence}/5`">
                  <i v-for="n in 5" :key="n" :class="{ on: n <= row.decision.confidence }" />
                </span>
              </template>
              <span v-else class="none">결정 안 함</span>
            </span>
            <span v-if="row.news" :class="['news', { alert: row.alert }]">
              {{ row.alert ? '철회 조건 충족' : '새 소식' }}
              <b class="num">{{ row.news }}</b>
            </span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.library {
  max-width: 920px;
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px 28px;
  margin-bottom: 26px;
}
h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-xl);
  letter-spacing: -0.02em;
}
.lead {
  margin: 6px 0 0;
  color: var(--ink-soft);
}
.lead b {
  font-weight: 500;
  color: var(--ink);
}
.lead .news-count {
  color: var(--accent);
}
.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
}
.seg {
  display: inline-flex;
  padding: 3px;
  background: var(--sheet-alt);
  border: 1px solid var(--rule);
  border-radius: 999px;
}
.seg button {
  padding: 6px 14px;
  font: inherit;
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--ink-soft);
  background: none;
  border: none;
  border-radius: 999px;
  cursor: pointer;
}
.seg button[aria-checked='true'] {
  color: #fff;
  background: var(--accent);
}
.search input {
  width: 140px;
  padding: 6px 2px;
  font-family: var(--font-num);
  text-transform: uppercase;
  background: color-mix(in srgb, var(--paper) 85%, transparent);
}
.search input::placeholder {
  font-family: var(--font-sans);
  text-transform: none;
}
.only {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--t-sm);
  color: var(--ink-soft);
  cursor: pointer;
  white-space: nowrap;
}
.state {
  padding: 28px;
  color: var(--ink-soft);
  background: var(--sheet);
  box-shadow: var(--shadow-sheet);
  border-radius: 6px;
}
.state.error {
  color: var(--down);
}

.group {
  margin-bottom: 22px;
  background: var(--sheet);
  box-shadow: var(--shadow-sheet);
  border-radius: 6px;
  border-top: 3px solid var(--accent);
}
.g-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 14px;
  padding: 16px 20px 10px;
}
h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  font-weight: 700;
}
h2.num {
  font-family: var(--font-num);
  font-weight: 500;
  letter-spacing: 0.02em;
}
.g-sub {
  font-size: var(--t-sm);
  color: var(--ink-faint);
}
.g-link {
  margin-left: auto;
  font-size: var(--t-sm);
}
.rows {
  margin: 0;
  padding: 0;
  list-style: none;
}
.row {
  display: grid;
  grid-template-columns: minmax(64px, 0.7fr) minmax(0, 1.2fr) minmax(0, 1.2fr) auto;
  align-items: center;
  gap: 14px;
  padding: 12px 20px;
  color: var(--ink);
  text-decoration: none;
  border-top: 1px solid var(--rule);
}
.row:hover {
  background: var(--sheet-alt);
}
.row:hover .r-ticker {
  color: var(--accent-deep);
}
.r-ticker {
  font-size: 17px;
  font-weight: 500;
}
.r-made,
.r-asof {
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.r-decision {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.none {
  font-size: var(--t-sm);
  color: var(--ink-faint);
}
.chip {
  display: inline-block;
  padding: 1px 9px;
  font-size: var(--t-xs);
  font-weight: 600;
  border-radius: 999px;
  border: 1px solid currentColor;
}
.chip.buy {
  color: var(--buy);
  background: color-mix(in srgb, var(--buy) 8%, transparent);
}
.chip.hold {
  color: var(--hold);
  background: color-mix(in srgb, var(--hold) 8%, transparent);
}
.chip.sell {
  color: var(--sell);
  background: color-mix(in srgb, var(--sell) 8%, transparent);
}
.conf {
  display: inline-flex;
  gap: 3px;
}
.conf i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--rule);
}
.conf i.on {
  background: var(--accent);
}
.news {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 4px 3px 10px;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--accent-deep);
  background: var(--accent-wash);
  border-radius: 999px;
  white-space: nowrap;
}
.news b {
  min-width: 18px;
  padding: 0 5px;
  text-align: center;
  color: #fff;
  background: var(--accent);
  border-radius: 999px;
}
.news.alert {
  color: var(--down);
  background: color-mix(in srgb, var(--down) 9%, transparent);
}
.news.alert b {
  background: var(--down);
}
@media (max-width: 640px) {
  .row {
    grid-template-columns: 1fr auto;
    gap: 6px 12px;
    padding: 12px 16px;
  }
  .r-asof {
    grid-column: 1;
  }
  .r-decision {
    grid-column: 2;
    grid-row: 1;
    justify-self: end;
  }
  .news {
    grid-column: 2;
    justify-self: end;
  }
  .g-head {
    padding: 14px 16px 8px;
  }
}
</style>
