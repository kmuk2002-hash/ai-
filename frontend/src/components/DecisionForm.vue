<script setup lang="ts">
/**
 * 결정 메모. 리포트를 읽고 마지막에 서명하듯 결정을 기록한다.
 * 내 철회 조건은 같은 종목의 최신 결정 값으로 미리 채운다 (철회 조건 이어서 복사 원칙).
 */
import { computed, ref, watch } from 'vue'
import type { DecisionAction, HighlightGroup, StoredDecision, StoredReport } from '../types'
import { ACTION_LABEL, TAG_META } from '../types'
import { api } from '../api/client'

const props = defineProps<{
  report: StoredReport
  groups: HighlightGroup[]
  latest: StoredDecision | null
}>()

const emit = defineEmits<{ saved: [decision: StoredDecision] }>()

const actions = Object.keys(ACTION_LABEL) as DecisionAction[]
const CONF_LABEL = ['', '낮음', '다소 낮음', '보통', '높음', '매우 높음']

const action = ref<DecisionAction>('hold')
const weightPct = ref<number | null>(null)
const confidence = ref(3)
const myThesis = ref('')
const myBreaker = ref('')
const evidence = ref<string[]>([])
const saving = ref(false)
const error = ref<string | null>(null)
const savedAt = ref<string | null>(null)

watch(
  () => props.latest,
  (d) => {
    if (!d) return
    myBreaker.value = d.my_thesis_breaker
    if (!myThesis.value) myThesis.value = d.my_thesis
    if (weightPct.value === null && d.weight !== null) weightPct.value = Math.round(d.weight * 1000) / 10
  },
  { immediate: true },
)

const selectableGroups = computed(() => props.groups.filter((g) => g.id))

const weightValid = computed(
  () => weightPct.value === null || (weightPct.value as unknown) === '' || (weightPct.value >= 0 && weightPct.value <= 100),
)
const valid = computed(() => myThesis.value.trim().length > 0 && myBreaker.value.trim().length > 0 && weightValid.value)

const missing = computed(() => {
  const m: string[] = []
  if (!myThesis.value.trim()) m.push('내 투자 논리')
  if (!myBreaker.value.trim()) m.push('철회 조건')
  return m
})

function preview(g: HighlightGroup): string {
  const t = g.spans.map((s) => s.quoted_text).join(' … ')
  return t.length > 70 ? t.slice(0, 70) + '…' : t
}

async function submit() {
  if (!valid.value || saving.value) return
  saving.value = true
  error.value = null
  try {
    const w = weightPct.value === null || (weightPct.value as unknown) === '' ? null : weightPct.value / 100
    const saved = await api.createDecision({
      report_id: props.report.id,
      ticker: props.report.ticker,
      market: props.report.market,
      action: action.value,
      weight: w,
      confidence: confidence.value,
      my_thesis: myThesis.value.trim(),
      my_thesis_breaker: myBreaker.value.trim(),
      evidence_group_ids: evidence.value,
    })
    savedAt.value = new Date(saved.decided_at).toLocaleString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    emit('saved', saved)
  } catch (e) {
    error.value = `결정을 기록하지 못했어요. ${e instanceof Error ? e.message : String(e)}`
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="decision" novalidate @submit.prevent="submit">
    <fieldset class="actions">
      <legend>결정</legend>
      <div class="action-row">
        <label v-for="a in actions" :key="a" :class="['action', `action-${a}`, { selected: action === a }]">
          <input v-model="action" type="radio" name="action" :value="a" />
          {{ ACTION_LABEL[a] }}
        </label>
      </div>
    </fieldset>

    <div class="row">
      <label class="field weight">
        <span class="field-label">비중</span>
        <span class="with-unit">
          <input v-model.number="weightPct" class="num" type="number" min="0" max="100" step="0.5" placeholder="선택" />
          <span class="unit">%</span>
        </span>
      </label>
      <fieldset class="field conf">
        <legend class="field-label">확신도 <span class="conf-text">{{ CONF_LABEL[confidence] }}</span></legend>
        <div class="conf-boxes">
          <label v-for="n in 5" :key="n" :class="['conf-box', { on: n <= confidence }]" :title="`${n} / 5`">
            <input v-model="confidence" type="radio" name="confidence" :value="n" :aria-label="`확신도 ${n}`" />
          </label>
        </div>
      </fieldset>
    </div>

    <label class="field">
      <span class="field-label">내 투자 논리</span>
      <textarea v-model="myThesis" class="lined" rows="3" placeholder="이 결정을 내린 이유를 한두 문장으로" />
    </label>

    <label class="field">
      <span class="field-label">
        철회 조건
        <small v-if="latest" class="hint">지난 결정에서 이어 옴</small>
      </span>
      <textarea v-model="myBreaker" class="lined" rows="2" placeholder="이 논리가 틀렸다고 볼 구체적인 조건" />
    </label>

    <fieldset class="evidence">
      <legend class="field-label">근거로 삼은 형광펜</legend>
      <p v-if="!selectableGroups.length" class="empty">리포트에 형광펜을 남기면 여기서 결정의 근거로 연결할 수 있어요.</p>
      <label v-for="g in selectableGroups" :key="g.id!" class="ev">
        <input v-model="evidence" type="checkbox" :value="g.id" />
        <span :class="['ev-swatch', `tag-${g.tag}`]" :title="TAG_META[g.tag].label" aria-hidden="true" />
        <span class="ev-text">{{ preview(g) }}</span>
      </label>
    </fieldset>

    <div class="signoff">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-else-if="savedAt" class="ok" role="status">
        <span class="sign-line" aria-hidden="true" />
        {{ savedAt }} 기록함
      </p>
      <p v-else-if="missing.length" class="todo">{{ missing.join('과 ') }}을 적으면 기록할 수 있어요.</p>
      <button type="submit" class="btn primary block" :disabled="!valid || saving">
        {{ saving ? '기록하는 중' : '결정 기록하기' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.decision {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
fieldset {
  margin: 0;
  padding: 0;
  border: none;
  min-width: 0;
}
legend,
.field-label {
  display: block;
  padding: 0;
  margin-bottom: 6px;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
}
.action-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 1px solid var(--rule-strong);
  border-radius: 2px;
}
.action {
  position: relative;
  padding: 9px 0;
  text-align: center;
  font-family: var(--font-serif);
  font-size: var(--t-md);
  font-weight: 700;
  color: var(--ink-soft);
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease;
}
.action + .action {
  border-left: 1px solid var(--rule-strong);
}
.action input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.action:hover {
  color: var(--ink);
}
.action:focus-within {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.action.selected {
  color: var(--sheet);
}
.action-buy.selected { background: var(--buy); }
.action-hold.selected { background: var(--hold); }
.action-sell.selected { background: var(--sell); }

.row {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 18px;
}
.field {
  display: flex;
  flex-direction: column;
}
.with-unit {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.unit {
  color: var(--ink-faint);
}
.conf-text {
  margin-left: 4px;
  font-weight: 400;
  color: var(--ink);
}
.conf-boxes {
  display: flex;
  gap: 5px;
  padding-top: 8px;
}
.conf-box {
  position: relative;
  width: 22px;
  height: 22px;
  border: 1.5px solid var(--rule-strong);
  border-radius: 2px;
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}
.conf-box.on {
  background: var(--ink);
  border-color: var(--ink);
}
.conf-box input {
  position: absolute;
  inset: 0;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}
.conf-box:focus-within {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* 줄 노트처럼 괘선이 있는 입력칸 */
.lined {
  padding: 2px 2px 0;
  border-bottom: none;
  resize: vertical;
  font-family: var(--font-serif);
  font-size: var(--t-md);
  line-height: 30px;
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 29px,
    var(--rule) 29px,
    var(--rule) 30px
  );
  background-attachment: local;
}
.lined:focus {
  box-shadow: none;
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 29px,
    var(--accent) 29px,
    var(--accent) 30px
  );
}
.hint {
  margin-left: 6px;
  font-weight: 400;
  color: var(--accent);
}

.evidence {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ev {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 8px;
  align-items: start;
  font-size: var(--t-sm);
  line-height: 1.55;
  cursor: pointer;
}
.ev input {
  margin-top: 4px;
}
.ev-swatch {
  width: 14px;
  height: 8px;
  margin-top: 7px;
  border-radius: 4px 1px 3px 2px;
}
.ev-swatch.tag-support { background: var(--m-support); }
.ev-swatch.tag-concern { background: var(--m-concern); }
.ev-swatch.tag-to_verify { background: var(--m-to_verify); }
.ev-swatch.tag-disagree { background: var(--m-disagree); }
.ev-text {
  font-family: var(--font-serif);
}
.empty {
  margin: 0;
  font-size: var(--t-sm);
  color: var(--ink-faint);
  line-height: 1.6;
}

.signoff {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px dashed var(--rule-strong);
}
.signoff p {
  margin: 0;
  font-size: var(--t-sm);
}
.todo {
  color: var(--ink-faint);
}
.error {
  color: var(--down);
}
.ok {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink);
  font-family: var(--font-serif);
}
.sign-line {
  flex: 0 0 40px;
  height: 0;
  border-top: 1.5px solid var(--ink);
}
</style>
