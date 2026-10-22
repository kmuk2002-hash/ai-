<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, USE_MOCK } from '../api/client'
import type { AnalyzeEvent, Market, ReportListItem } from '../types'
import AnalyzeProgress from '../components/AnalyzeProgress.vue'

const router = useRouter()

function today(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const ticker = ref('')
const market = ref<Market>('US')
const asOf = ref(today())
const phase = ref<'idle' | 'running' | 'done'>('idle')
const compared = ref<boolean | null>(null)
/** 끝난 노드 → 끝난 시각(초). SSE 이벤트로 채운다 */
const finished = ref<Record<string, number>>({})
/** 펀더멘털 서브그래프에서 마지막으로 끝난 단계와 재검색 횟수 */
const fundStep = ref<string | null>(null)
const retries = ref(0)
const hasPast = ref<boolean | null>(null)
const elapsed = ref(0)
const error = ref<string | null>(null)
const recent = ref<ReportListItem[]>([])
const recentLoaded = ref(false)

let timer: number | undefined

onMounted(async () => {
  try {
    recent.value = (await api.listReports()).slice(0, 8)
  } catch {
    /* 목록은 없어도 분석은 가능 */
  } finally {
    recentLoaded.value = true
  }
})

onBeforeUnmount(() => window.clearInterval(timer))

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

async function analyze() {
  const t = ticker.value.trim().toUpperCase()
  if (!t || phase.value !== 'idle') return
  phase.value = 'running'
  compared.value = null
  finished.value = {}
  fundStep.value = null
  retries.value = 0
  hasPast.value = null
  error.value = null
  elapsed.value = 0
  const startedAt = Date.now()
  timer = window.setInterval(() => (elapsed.value = Math.floor((Date.now() - startedAt) / 1000)), 250)
  try {
    const report = await api.analyzeStream({ ticker: t, market: market.value, as_of_date: asOf.value }, onEvent)
    window.clearInterval(timer)
    compared.value = report.past_decision_review !== null
    phase.value = 'done'
    // 완료 표시가 순서대로 찍히는 것을 잠깐 보여준 뒤 이동
    if (!reduceMotion()) await new Promise((r) => setTimeout(r, 900))
    await router.push({ name: 'report', params: { id: report.id } })
  } catch (e) {
    window.clearInterval(timer)
    error.value = e instanceof Error ? e.message : String(e)
    phase.value = 'idle'
  }
}

function onEvent(e: AnalyzeEvent) {
  if (e.type === 'step') {
    fundStep.value = e.step
    if (e.step === 'query_rewrite') retries.value += 1
    return
  }
  finished.value = { ...finished.value, [e.node]: e.elapsed }
  if (e.node === 'past_decision' && e.has_past !== undefined) hasPast.value = e.has_past
}

function fmtDate(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}월 ${d.getDate()}일`
}
</script>

<template>
  <div class="page analyze">
    <section class="intro">
      <h1>어떤 종목을 볼까요?</h1>
      <p class="lead">
        펀더멘털과 퀀트 관점으로 리포트를 만들어요. 같은 종목을 전에 기록했다면, 그때 정한 철회 조건이 지금도 유효한지 함께 점검해요.
      </p>

      <form class="form" @submit.prevent="analyze">
        <label class="field ticker">
          <span>티커</span>
          <input
            v-model="ticker"
            :disabled="phase !== 'idle'"
            placeholder="NVDA"
            autocomplete="off"
            spellcheck="false"
            required
            aria-describedby="ticker-hint"
          />
        </label>
        <label class="field">
          <span>시장</span>
          <select v-model="market" :disabled="phase !== 'idle'">
            <option value="US">미국</option>
            <option value="KR" disabled>한국 (준비 중)</option>
          </select>
        </label>
        <label class="field">
          <span>기준일</span>
          <input v-model="asOf" class="num" type="date" :disabled="phase !== 'idle'" required />
        </label>
        <button class="btn primary submit" type="submit" :disabled="phase !== 'idle' || !ticker.trim()">
          {{ phase === 'idle' ? '분석하기' : '분석 중' }}
        </button>
      </form>
      <p v-if="USE_MOCK && phase === 'idle'" id="ticker-hint" class="hint">
        목업 데이터에서는 <b>NVDA</b>에 지난 결정이 있어요. 다른 티커는 처음 분석하는 종목으로 동작해요.
      </p>

      <AnalyzeProgress
        v-if="phase !== 'idle'"
        :phase="phase === 'done' ? 'done' : 'running'"
        :elapsed="elapsed"
        :compared="compared"
        :finished="finished"
        :fund-step="fundStep"
        :retries="retries"
        :has-past="hasPast"
      />

      <div v-if="error" class="error" role="alert">
        <b>분석을 마치지 못했어요.</b>
        <span>{{ error }}</span>
        <span class="error-help">백엔드 서버(localhost:8000)가 켜져 있는지 확인한 뒤 다시 시도하세요.</span>
      </div>
    </section>

    <section class="recent-wrap" aria-labelledby="recent-title">
      <div class="recent-head">
        <h2 id="recent-title">최근 리포트</h2>
        <RouterLink :to="{ name: 'library' }">기록 보관함에서 모두 보기</RouterLink>
      </div>
      <p v-if="recentLoaded && !recent.length" class="empty">아직 만든 리포트가 없어요. 위에서 첫 종목을 분석해 보세요.</p>
      <ul v-else class="recent">
        <li v-for="r in recent" :key="r.id">
          <RouterLink class="r-main" :to="{ name: 'report', params: { id: r.id } }">
            <span class="r-ticker">{{ r.ticker }}</span>
            <span class="r-market">{{ r.market }}</span>
            <span class="r-date num">기준일 {{ r.as_of_date }}</span>
          </RouterLink>
          <span class="r-made">{{ fmtDate(r.created_at) }} 작성</span>
          <RouterLink class="r-hist" :to="{ name: 'history', params: { market: r.market, ticker: r.ticker } }">결정 이력</RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.analyze {
  max-width: 820px;
}
.intro {
  padding: 40px 44px 36px;
  background: var(--sheet);
  box-shadow: var(--shadow-sheet);
  border-top: 3px solid var(--accent);
  border-radius: 8px;
}
@media (max-width: 640px) {
  .intro {
    padding: 26px 18px 24px;
  }
}
h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-xl);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.lead {
  max-width: 56ch;
  margin: 10px 0 30px;
  color: var(--ink-soft);
  line-height: 1.75;
}
.form {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 0.9fr) minmax(0, 1fr) auto;
  gap: 22px;
  align-items: end;
}
@media (max-width: 640px) {
  .form {
    grid-template-columns: 1fr 1fr;
    gap: 18px 16px;
  }
  .ticker,
  .submit {
    grid-column: 1 / -1;
  }
}
.field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.field > span {
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
}
.ticker input {
  font-family: var(--font-num);
  font-size: 26px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 2px 6px;
}
.ticker input::placeholder {
  color: var(--rule-strong);
}
.hint {
  margin: 18px 0 0;
  font-size: var(--t-sm);
  color: var(--ink-faint);
}
.hint b {
  font-family: var(--font-num);
  font-weight: 500;
  color: var(--ink-soft);
}
.error {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 22px;
  padding: 12px 14px;
  font-size: var(--t-sm);
  color: var(--ink);
  border-left: 3px solid var(--down);
  background: color-mix(in srgb, var(--down) 7%, transparent);
}
.error b {
  color: var(--down);
}
.error-help {
  color: var(--ink-soft);
}

.recent-wrap {
  margin-top: 28px;
  padding: 22px 28px 12px;
  background: color-mix(in srgb, var(--sheet) 92%, transparent);
  border-radius: 8px;
  box-shadow: var(--shadow-sheet);
}
.recent-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: var(--t-sm);
}
@media (max-width: 640px) {
  .recent-wrap {
    padding: 18px 16px 8px;
  }
}
h2 {
  margin: 0 0 6px;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  font-weight: 700;
}
.empty {
  margin: 8px 0 0;
  color: var(--ink-faint);
}
.recent {
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: 2px solid var(--ink);
}
.recent li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 18px;
  align-items: baseline;
  padding: 12px 0;
  border-bottom: 1px solid var(--rule);
}
.r-main {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
  color: var(--ink);
  text-decoration: none;
}
.r-main:hover .r-ticker {
  text-decoration: underline;
  text-underline-offset: 4px;
}
.r-ticker {
  font-family: var(--font-num);
  font-size: 17px;
  font-weight: 500;
}
.r-market {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.r-date {
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.r-made {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.r-hist {
  font-size: var(--t-sm);
}
@media (max-width: 520px) {
  .recent li {
    grid-template-columns: 1fr auto;
    gap: 4px 12px;
  }
  .r-made {
    grid-row: 2;
  }
  .r-hist {
    grid-row: 1 / span 2;
    align-self: center;
  }
  .r-date {
    display: none;
  }
}
</style>
