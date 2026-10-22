<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api/client'
import type { HighlightGroup, Market, StoredDecision } from '../types'
import { ACTION_LABEL, FIELD_LABEL, TAG_META } from '../types'

const props = defineProps<{ market: Market; ticker: string }>()

const decisions = ref<StoredDecision[]>([])
const groupsByReport = ref<Record<string, HighlightGroup[]>>({})
const loading = ref(true)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    const list = await api.listDecisions(props.ticker, props.market)
    decisions.value = list
    const reportIds = [...new Set(list.map((d) => d.report_id))]
    const entries = await Promise.all(
      reportIds.map(async (id) => [id, await api.listHighlights(id).catch(() => [])] as const),
    )
    groupsByReport.value = Object.fromEntries(entries)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

watch(() => [props.market, props.ticker], load, { immediate: true })

function evidenceOf(d: StoredDecision): HighlightGroup[] {
  const groups = groupsByReport.value[d.report_id] ?? []
  return groups.filter((g) => g.id && d.evidence_group_ids.includes(g.id))
}

function dateParts(iso: string) {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return { ymd: `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())}`, hm: `${p(d.getHours())}:${p(d.getMinutes())}` }
}

/** 직전 결정과 철회 조건이 달라졌는지 */
function breakerChanged(i: number): boolean {
  const next = decisions.value[i + 1]
  return !!next && next.my_thesis_breaker !== decisions.value[i].my_thesis_breaker
}

const latestBreaker = computed(() => decisions.value[0]?.my_thesis_breaker ?? null)
const marketLabel = computed(() => (props.market === 'US' ? '미국' : '한국'))
</script>

<template>
  <div class="page veil history">
    <header class="head">
      <div>
        <h1>{{ ticker }}</h1>
        <p class="meta">
          <span>{{ marketLabel }}</span>
          <span>{{ decisions.length ? `결정 이력 ${decisions.length}건` : '결정 이력' }}</span>
        </p>
      </div>
      <RouterLink class="btn ghost" to="/">새로 분석하기</RouterLink>
    </header>

    <div v-if="loading" class="state" aria-busy="true">이력을 불러오는 중이에요.</div>

    <div v-else-if="error" class="state error" role="alert">
      <b>이력을 불러오지 못했어요.</b>
      <span>{{ error }}</span>
      <button type="button" class="btn ghost" @click="load">다시 불러오기</button>
    </div>

    <div v-else-if="!decisions.length" class="state empty">
      <p>{{ ticker }}에 대해 기록한 결정이 아직 없어요.</p>
      <p class="empty-sub">리포트를 읽고 결정 메모를 기록하면 여기에 장부처럼 쌓여요.</p>
      <RouterLink class="btn primary" to="/">{{ ticker }} 분석하기</RouterLink>
    </div>

    <template v-else>
      <section v-if="latestBreaker" class="current" aria-labelledby="current-title">
        <h2 id="current-title">지금 지켜보는 철회 조건</h2>
        <p>{{ latestBreaker }}</p>
      </section>

      <div class="ledger-head" aria-hidden="true">
        <span>날짜</span>
        <span>결정</span>
        <span>내용</span>
      </div>
      <ol class="timeline">
        <li v-for="(d, i) in decisions" :key="d.id" class="item">
          <div class="entry">
            <div class="col-date">
              <time class="num" :datetime="d.decided_at">{{ dateParts(d.decided_at).ymd }}</time>
              <span class="time num">{{ dateParts(d.decided_at).hm }}</span>
            </div>

            <div class="col-action">
              <span :class="['action', `action-${d.action}`]">{{ ACTION_LABEL[d.action] }}</span>
              <span class="conf" :aria-label="`확신도 ${d.confidence} / 5`" :title="`확신도 ${d.confidence} / 5`">
                <span v-for="n in 5" :key="n" :class="['tick', { on: n <= d.confidence }]" />
              </span>
              <span v-if="d.weight !== null" class="weight num">비중 {{ (d.weight * 100).toFixed(1) }}%</span>
            </div>

            <div class="col-body">
              <p class="thesis">{{ d.my_thesis }}</p>
              <p class="breaker">
                <span class="k">철회 조건</span>
                {{ d.my_thesis_breaker }}
                <span v-if="breakerChanged(i)" class="changed">이번에 바꿈</span>
              </p>

              <ul v-if="evidenceOf(d).length" class="evidence" aria-label="근거로 삼은 형광펜">
                <li v-for="g in evidenceOf(d)" :key="g.id!">
                  <span v-for="(s, j) in g.spans" :key="j" class="ev-quote">
                    <span :class="['mk', `mk-${g.tag}`]">{{ s.quoted_text }}</span>
                    <small>{{ FIELD_LABEL[s.field] }}</small>
                  </span>
                  <span class="ev-meta">
                    {{ TAG_META[g.tag].label }}<template v-if="g.comment">, {{ g.comment }}</template>
                  </span>
                </li>
              </ul>

              <RouterLink class="report-link" :to="{ name: 'report', params: { id: d.report_id } }">당시 리포트 열기</RouterLink>
            </div>
          </div>
        </li>
      </ol>
    </template>
  </div>
</template>

<style scoped>
.history {
  max-width: 960px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
h1 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-hero);
  font-weight: 700;
  line-height: 1.1;
}
.meta {
  display: flex;
  gap: 14px;
  margin: 8px 0 0;
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.meta > span + span {
  padding-left: 14px;
  border-left: 1px solid var(--rule-strong);
}
@media (max-width: 600px) {
  h1 {
    font-size: 36px;
  }
}

.current {
  margin-bottom: 32px;
  padding: 18px 22px;
  background: var(--sheet);
  border-left: 3px solid var(--margin-rule);
  box-shadow: var(--shadow-sheet);
}
.current h2 {
  margin: 0 0 4px;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
}
.current p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  line-height: 1.55;
}

/* 장부 */
.ledger-head,
.entry {
  display: grid;
  grid-template-columns: 112px 128px minmax(0, 1fr);
}
.ledger-head {
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
  padding-bottom: 8px;
  border-bottom: 2px solid var(--ink);
}
.ledger-head span + span,
.col-action,
.col-body {
  padding-left: 18px;
  border-left: 1px solid var(--rule);
}
.ledger-head span + span {
  border-left-color: transparent;
}
.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}
.item {
  border-bottom: 1px solid var(--rule);
}
.entry {
  padding: 0;
}
.entry > div {
  padding-top: 18px;
  padding-bottom: 20px;
}
.col-date {
  display: flex;
  flex-direction: column;
}
.col-date time {
  font-size: var(--t-md);
}
.time {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.col-action {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.action {
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  font-weight: 700;
  line-height: 1.2;
}
.action-buy { color: var(--buy); }
.action-hold { color: var(--hold); }
.action-sell { color: var(--sell); }
.conf {
  display: flex;
  gap: 3px;
}
.tick {
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--rule-strong);
  border-radius: 1px;
}
.tick.on {
  background: var(--ink);
  border-color: var(--ink);
}
.weight {
  font-size: var(--t-xs);
  color: var(--ink-soft);
}
.col-body p {
  margin: 0;
}
.thesis {
  font-family: var(--font-serif);
  font-size: var(--t-md);
  line-height: 1.7;
}
.breaker {
  margin-top: 6px !important;
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.k {
  margin-right: 6px;
  font-weight: 600;
  color: var(--ink);
}
.changed {
  margin-left: 6px;
  padding: 0 6px;
  font-size: var(--t-xs);
  color: var(--accent);
  border: 1px solid currentColor;
  border-radius: 2px;
}
.evidence {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 14px 0 0;
  padding: 12px 0 0;
  list-style: none;
  border-top: 1px dashed var(--rule);
}
.evidence li {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ev-quote {
  font-family: var(--font-serif);
  font-size: var(--t-sm);
  line-height: 1.75;
}
.ev-quote small {
  margin-left: 6px;
  font-family: var(--font-sans);
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.mk {
  padding: 0.06em 0.15em;
  border-radius: 0.45em 0.16em 0.4em 0.2em / 0.3em 0.45em 0.22em 0.4em;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
.mk-support { background: var(--m-support); }
.mk-concern { background: var(--m-concern); }
.mk-to_verify { background: var(--m-to_verify); }
.mk-disagree { background: var(--m-disagree); }
.ev-meta {
  font-size: var(--t-xs);
  color: var(--ink-soft);
}
.report-link {
  display: inline-block;
  margin-top: 14px;
  font-size: var(--t-sm);
}

@media (max-width: 640px) {
  .ledger-head {
    display: none;
  }
  .timeline {
    border-top: 2px solid var(--ink);
  }
  .entry {
    grid-template-columns: auto 1fr;
    column-gap: 14px;
  }
  .entry > div {
    padding-top: 14px;
    padding-bottom: 0;
  }
  .col-date {
    flex-direction: row;
    gap: 8px;
    align-items: baseline;
  }
  .col-action {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    justify-content: flex-end;
    padding-left: 0;
    border-left: none;
  }
  .action {
    font-size: var(--t-md);
  }
  .col-body {
    grid-column: 1 / -1;
    padding: 8px 0 18px !important;
    border-left: none;
  }
}

.state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 28px 0;
  color: var(--ink-soft);
}
.state.error b {
  color: var(--down);
}
.empty p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-lg);
  color: var(--ink);
}
.empty .empty-sub {
  margin-bottom: 10px;
  font-family: var(--font-sans);
  font-size: var(--t-md);
  color: var(--ink-soft);
}
</style>
