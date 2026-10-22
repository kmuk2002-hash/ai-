<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api } from '../api/client'
import type {
  HighlightGroup,
  HighlightTag,
  ReportField,
  StoredDecision,
  StoredReport,
} from '../types'
import { ACTION_LABEL, CATEGORY_LABEL, FIELD_LABEL, STATUS_LABEL } from '../types'
import { useNotices } from '../composables/notices'
import { shortDate } from '../lib/format'
import { useHighlight } from '../composables/useHighlight'
import ReportSection from '../components/ReportSection.vue'
import HighlightPopover from '../components/HighlightPopover.vue'
import HighlightList from '../components/HighlightList.vue'
import QuantCards from '../components/QuantCards.vue'
import DecisionForm from '../components/DecisionForm.vue'

const props = defineProps<{ id: string }>()
const route = useRoute()

// 이 리포트로 내린 결정 이후 다시 분석해서 생긴 소식
const { forReport, markRead, isRead } = useNotices()
const since = computed(() => forReport(props.id))

const report = ref<StoredReport | null>(null)
const groups = ref<HighlightGroup[]>([])
const latest = ref<StoredDecision | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const activeGroupId = ref<string | null>(null)
const savingHighlight = ref(false)
const freshGroupId = ref<string | null>(null)
let freshTimer: number | undefined

const MAIN_FIELDS: ReportField[] = ['investment_thesis', 'risks', 'consensus_gap', 'thesis_breakers']

const rawTexts = computed<Partial<Record<ReportField, string>>>(() => {
  const r = report.value
  if (!r) return {}
  return {
    investment_thesis: r.investment_thesis,
    risks: r.risks,
    consensus_gap: r.consensus_gap,
    thesis_breakers: r.thesis_breakers,
    ...(r.past_decision_review ? { past_decision_review: r.past_decision_review.summary } : {}),
  }
})

const bodyRef = ref<HTMLElement | null>(null)
const { pending, onSelectionEnd, clear } = useHighlight(bodyRef, () => rawTexts.value)

async function load(id: string) {
  loading.value = true
  error.value = null
  activeGroupId.value = null
  pending.value = null
  try {
    const r = await api.getReport(id)
    report.value = r
    const [hl, decisions] = await Promise.all([api.listHighlights(id), api.listDecisions(r.ticker, r.market)])
    groups.value = hl
    latest.value = decisions[0] ?? null
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
  if (route.hash === '#since') {
    await nextTick()
    document.getElementById('since')?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }
}

watch(() => props.id, load, { immediate: true })

async function saveHighlight(payload: { tag: HighlightTag; comment: string | null }) {
  if (!report.value || !pending.value) return
  savingHighlight.value = true
  try {
    const g = await api.createHighlight(report.value.id, { ...payload, spans: pending.value.spans })
    groups.value = [...groups.value, g]
    activeGroupId.value = g.id
    freshGroupId.value = g.id
    window.clearTimeout(freshTimer)
    freshTimer = window.setTimeout(() => (freshGroupId.value = null), 900)
    clear()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    savingHighlight.value = false
  }
}

/** 목록에서 그룹을 고르면 본문의 첫 조각으로 스크롤 */
function selectFromList(id: string) {
  activeGroupId.value = id
  document
    .querySelector(`[data-groups~="${CSS.escape(id)}"]`)
    ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

// 팝오버 바깥을 누르면 저장 대기 하이라이트 취소 (팝오버 내부 mousedown은 전파되지 않음)
function onDocMouseDown() {
  if (pending.value) pending.value = null
}
onMounted(() => document.addEventListener('mousedown', onDocMouseDown))
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocMouseDown)
  window.clearTimeout(freshTimer)
})

function onDecisionSaved(d: StoredDecision) {
  latest.value = d
}

function sourceLabel(doc: string) {
  return { '10-K': '10-K', '10-Q': '10-Q', broker_report: '증권사 리포트', web: '웹', quant_api: '퀀트 API' }[doc] ?? doc
}

const STATUS_MARK = { triggered: '●', not_triggered: '○', insufficient_evidence: '◌' } as const

const asOfLabel = computed(() => {
  const d = report.value?.as_of_date
  if (!d) return ''
  const [y, m, day] = d.split('-').map(Number)
  return `${y}년 ${m}월 ${day}일 기준`
})
</script>

<template>
  <div class="page veil report-page">
    <!-- 불러오는 중: 괘선만 있는 빈 장부 -->
    <div v-if="loading" class="skeleton" aria-busy="true" aria-label="리포트를 불러오는 중">
      <div class="sk-title" />
      <div class="sk-strip" />
      <div class="sk-sheet">
        <span v-for="n in 9" :key="n" class="sk-line" :style="{ width: `${60 + ((n * 37) % 38)}%` }" />
      </div>
    </div>

    <div v-else-if="error && !report" class="load-error" role="alert">
      <h1>리포트를 열 수 없어요</h1>
      <p>{{ error }}</p>
      <div class="load-error-actions">
        <button type="button" class="btn ghost" @click="load(props.id)">다시 불러오기</button>
        <RouterLink class="btn primary" to="/">새로 분석하기</RouterLink>
      </div>
    </div>

    <template v-else-if="report">
      <header class="head">
        <div class="head-main">
          <h1>{{ report.ticker }}</h1>
          <p class="meta">
            <span class="meta-market">{{ report.market === 'US' ? '미국' : '한국' }}</span>
            <span>{{ asOfLabel }}</span>
            <span v-if="report.quant_snapshot.sector">{{ report.quant_snapshot.sector }}<template v-if="report.quant_snapshot.industry">, {{ report.quant_snapshot.industry }}</template></span>
          </p>
        </div>
        <RouterLink class="btn ghost" :to="{ name: 'history', params: { market: report.market, ticker: report.ticker } }">
          결정 이력 보기
        </RouterLink>
      </header>

      <section v-if="since.length" id="since" class="since" aria-labelledby="since-title">
        <h2 id="since-title">이 결정 이후 확인된 내용</h2>
        <article v-for="n in since" :key="n.id" :class="['notice', n.level, { read: isRead(n.id) }]">
          <header class="n-head">
            <span class="n-title">
              {{ shortDate(n.decided_at) }} {{ ACTION_LABEL[n.action] }} 결정 →
              {{ shortDate(n.created_at) }} 재분석에서
              <b>{{ n.level === 'alert' ? '철회 조건이 충족됐어요' : n.triggered.length ? `${n.triggered.length}개 항목이 해당돼요` : '해당하는 항목이 없어요' }}</b>
            </span>
            <span class="n-actions">
              <RouterLink class="btn ghost small" :to="{ name: 'report', params: { id: n.report_id } }" @click="markRead(n.id)">새 리포트 열기</RouterLink>
              <button v-if="!isRead(n.id)" type="button" class="btn primary small" @click="markRead(n.id)">확인했어요</button>
            </span>
          </header>
          <ul v-if="n.triggered.length" class="n-checks">
            <li v-for="(c, i) in n.triggered" :key="i">
              <span :class="['n-cat', c.category]">{{ CATEGORY_LABEL[c.category] }}</span>
              <span class="n-target">{{ c.target }}</span>
              <span class="n-evidence">{{ c.evidence }}</span>
            </li>
          </ul>
          <p v-else class="n-summary">{{ n.summary }}</p>
        </article>
      </section>

      <QuantCards :q="report.quant_snapshot" />

      <div class="layout">
        <article ref="bodyRef" class="body" @mouseup="onSelectionEnd" @keyup="onSelectionEnd">
          <p class="tip">문장을 드래그하면 형광펜을 긋고 메모를 남길 수 있어요.</p>

          <div class="sections">
            <ReportSection
              v-for="f in MAIN_FIELDS"
              :key="f"
              :field="f"
              :title="FIELD_LABEL[f]"
              :text="rawTexts[f] ?? ''"
              :groups="groups"
              :active-group-id="activeGroupId"
              :fresh-group-id="freshGroupId"
              @select="activeGroupId = $event"
            />
          </div>

          <section v-if="report.past_decision_review" class="review" aria-label="과거 결정 대비">
            <ReportSection
              field="past_decision_review"
              title="과거 결정 대비"
              :text="report.past_decision_review.summary"
              :groups="groups"
              :active-group-id="activeGroupId"
              :fresh-group-id="freshGroupId"
              @select="activeGroupId = $event"
            />
            <div class="verdicts">
              <table class="checks">
                <caption class="sr-only">지난 결정 점검표</caption>
                <thead>
                  <tr>
                    <th scope="col">점검</th>
                    <th scope="col">대상</th>
                    <th scope="col">판정</th>
                    <th scope="col">근거</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(c, i) in report.past_decision_review.checks" :key="i" :class="`row-${c.status}`">
                    <td class="cat" data-label="점검">{{ CATEGORY_LABEL[c.category] }}</td>
                    <td class="target" data-label="대상">{{ c.target }}</td>
                    <td class="status" data-label="판정">
                      <span :class="['badge', `st-${c.status}`]"><span aria-hidden="true">{{ STATUS_MARK[c.status] }}</span> {{ STATUS_LABEL[c.status] }}</span>
                    </td>
                    <td class="evidence" data-label="근거">{{ c.evidence }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="sources" aria-label="출처">
            <h3 class="margin-title">출처</h3>
            <ul>
              <li v-for="(s, i) in report.sources" :key="i">
                <span class="src-type">{{ sourceLabel(s.doc_type) }}</span>
                <span class="src-title">
                  <a v-if="s.url" :href="s.url" target="_blank" rel="noopener">{{ s.title }}</a>
                  <template v-else>{{ s.title }}</template>
                  <span v-if="s.section" class="src-section">{{ s.section }}</span>
                </span>
              </li>
            </ul>
          </section>
        </article>

        <aside class="side">
          <section class="notes" aria-labelledby="notes-title">
            <h2 id="notes-title">형광펜 <span class="count num">{{ groups.length }}</span></h2>
            <HighlightList :groups="groups" :active-group-id="activeGroupId" @select="selectFromList" />
          </section>
          <section class="memo" aria-labelledby="memo-title">
            <h2 id="memo-title">결정 메모</h2>
            <p class="memo-sub">{{ report.ticker }}, {{ asOfLabel }} 리포트를 읽고</p>
            <DecisionForm :key="report.id" :report="report" :groups="groups" :latest="latest" @saved="onDecisionSaved" />
          </section>
        </aside>
      </div>
    </template>

    <Transition name="slip">
      <HighlightPopover
        v-if="pending"
        :key="pending.spans.map((s) => s.field + s.start_offset).join()"
        :x="pending.x"
        :y="pending.y"
        :spans="pending.spans"
        :saving="savingHighlight"
        @save="saveHighlight"
        @cancel="clear"
      />
    </Transition>
  </div>
</template>

<style scoped>
.report-page {
  --margin-col: 132px;
}
@media (max-width: 640px) {
  .report-page {
    --margin-col: 0px;
  }
}

/* 머리 */
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-hero);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.01em;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 8px 0 0;
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.meta > span + span {
  padding-left: 14px;
  border-left: 1px solid var(--rule-strong);
}
.meta-market {
  font-weight: 600;
  color: var(--ink);
}
@media (max-width: 600px) {
  h1 {
    font-size: 36px;
  }
}

/* 본문 + 레일 */
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 36px;
  margin-top: 28px;
  align-items: start;
}
@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
    gap: 28px;
  }
}

/* 리포트 종이 */
.body {
  padding: 30px 40px 12px 0;
  background: var(--sheet);
  box-shadow: var(--shadow-sheet);
  animation: sheet-in 0.5s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
@keyframes sheet-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}
@media (max-width: 640px) {
  .body {
    padding: 22px 16px 8px 0;
  }
}
.tip {
  margin: 0 0 18px calc(var(--margin-col) + 25px);
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
@media (max-width: 640px) {
  .tip {
    margin-left: 16px;
  }
}
.sections {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

/* 과거 결정 대비: 종이 위에 덧붙인 검토 쪽지 */
.review {
  margin: 34px -40px 0 0;
  padding: 26px 40px 22px 0;
  border-top: 2px solid var(--ink);
  background: linear-gradient(var(--accent-wash), var(--accent-wash));
}
.verdicts {
  margin: 18px 0 0 calc(var(--margin-col) + 25px);
}
@media (max-width: 640px) {
  .review {
    margin-right: -16px;
    padding-right: 16px;
  }
  .verdicts {
    margin-left: 16px;
  }
}
.checks {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--t-sm);
  line-height: 1.55;
}
.checks th {
  text-align: left;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
  padding: 0 10px 8px 0;
  border-bottom: 1px solid var(--ink);
}
.checks td {
  padding: 10px 10px 10px 0;
  vertical-align: top;
  border-bottom: 1px solid var(--rule);
}
.checks .cat {
  white-space: nowrap;
  font-weight: 600;
}
.checks .target {
  font-family: var(--font-serif);
  min-width: 12em;
}
.checks .evidence {
  color: var(--ink-soft);
}
.badge {
  white-space: nowrap;
  font-weight: 600;
}
.st-triggered { color: var(--down); }
.st-not_triggered { color: var(--up); }
.st-insufficient_evidence { color: var(--ink-faint); }

/* 좁은 화면: 표 대신 항목별 블록 */
@media (max-width: 720px) {
  .checks thead {
    display: none;
  }
  .checks,
  .checks tbody,
  .checks tr,
  .checks td {
    display: block;
    width: 100%;
  }
  .checks tr {
    position: relative;
    padding: 12px 0;
    border-bottom: 1px solid var(--rule);
  }
  .checks td {
    padding: 2px 0;
    border: none;
    min-width: 0;
  }
  .checks .cat {
    padding-right: 128px;
  }
  .checks .status {
    position: absolute;
    top: 12px;
    right: 0;
    width: auto;
  }
  .checks .evidence::before {
    content: '근거  ';
    color: var(--ink-faint);
  }
}

/* 출처 */
.sources {
  display: grid;
  grid-template-columns: var(--margin-col) minmax(0, 1fr);
  margin-top: 30px;
  padding: 18px 0 10px;
  border-top: 1px solid var(--rule);
}
.margin-title {
  margin: 0;
  padding: 2px 20px 0 0;
  font-size: var(--t-sm);
  font-weight: 600;
  color: var(--ink-soft);
  text-align: right;
}
.sources ul {
  margin: 0;
  padding: 0 0 0 25px;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: var(--t-sm);
}
.sources li {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 8px;
}
.src-type {
  color: var(--ink-faint);
}
.src-section {
  margin-left: 8px;
  color: var(--ink-faint);
}
@media (max-width: 640px) {
  .sources {
    grid-template-columns: 1fr;
  }
  .margin-title {
    padding: 0 0 6px 16px;
    text-align: left;
  }
  .sources ul {
    padding-left: 16px;
  }
  .sources li {
    grid-template-columns: 1fr;
    gap: 0;
  }
}

/* 오른쪽 레일 */
.side {
  display: flex;
  flex-direction: column;
  gap: 32px;
  position: sticky;
  top: 76px;
}
@media (max-width: 1000px) {
  .side {
    position: static;
  }
}
.side h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  font-weight: 700;
}
.notes h2 {
  padding-bottom: 8px;
  margin-bottom: 4px;
  border-bottom: 2px solid var(--ink);
}
.count {
  margin-left: 4px;
  font-size: var(--t-sm);
  font-weight: 400;
  color: var(--ink-faint);
}
.memo {
  padding: 20px 20px 22px;
  background: var(--sheet);
  border-top: 3px solid var(--ink);
  box-shadow: var(--shadow-sheet);
}
.memo-sub {
  margin: 2px 0 18px;
  font-size: var(--t-xs);
  color: var(--ink-faint);
}

/* 상태 화면 */
.skeleton {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.sk-title {
  width: 160px;
  height: 44px;
  background: var(--rule);
  opacity: 0.6;
}
.sk-strip {
  height: 64px;
  border-top: 2px solid var(--rule-strong);
  border-bottom: 1px solid var(--rule);
}
.sk-sheet {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 34px 40px 34px calc(132px + 25px);
  background: var(--sheet);
  box-shadow: var(--shadow-sheet);
}
.sk-line {
  height: 10px;
  background: var(--rule);
  border-radius: 2px;
  animation: sk 1.4s ease-in-out infinite alternate;
}
@keyframes sk {
  to {
    opacity: 0.45;
  }
}
@media (max-width: 640px) {
  .sk-sheet {
    padding: 24px 16px;
  }
}
.load-error {
  max-width: 560px;
  padding: 36px 0;
}
.load-error h1 {
  font-size: var(--t-xl);
}
.load-error p {
  color: var(--ink-soft);
}
.load-error-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

/* 팝오버 전환 */
.slip-enter-active {
  transition: opacity 0.16s ease, transform 0.16s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.slip-leave-active {
  transition: opacity 0.1s ease;
}
.slip-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.slip-leave-to {
  opacity: 0;
}

/* 결정 이후 소식 */
.since {
  margin: 0 0 22px;
  scroll-margin-top: 80px;   /* 상단 고정 메뉴에 가리지 않게 */
}
.since h2 {
  margin: 0 0 10px;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
}
.notice {
  margin-bottom: 10px;
  padding: 14px 18px;
  background: var(--sheet);
  border-left: 4px solid var(--accent);
  border-radius: 6px;
  box-shadow: var(--shadow-sheet);
}
.notice.alert {
  border-left-color: var(--down);
  background: color-mix(in srgb, var(--down) 4%, var(--sheet));
}
.notice.read {
  border-left-color: var(--rule-strong);
}
.n-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}
.n-title {
  color: var(--ink-soft);
}
.n-title b {
  color: var(--ink);
}
.notice.alert:not(.read) .n-title b {
  color: var(--down);
}
.n-actions {
  display: flex;
  gap: 8px;
}
.btn.small {
  padding: 5px 12px;
  font-size: var(--t-sm);
}
.n-checks {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}
.n-checks li {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 2px 14px;
  padding: 8px 0;
  border-top: 1px solid var(--rule);
}
.n-cat {
  grid-row: span 2;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--accent-deep);
}
.n-cat.thesis_breaker {
  color: var(--down);
}
.n-target {
  font-weight: 600;
}
.n-evidence,
.n-summary {
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.n-summary {
  margin: 10px 0 0;
  white-space: pre-line;
}
@media (max-width: 560px) {
  .n-checks li {
    grid-template-columns: 1fr;
  }
  .n-cat {
    grid-row: auto;
  }
}
</style>
