<script setup lang="ts">
/**
 * 분석 진행 표시. 에이전트 그래프 구조를 그대로 보여준다:
 *   펀더멘털 · 퀀트 · 과거 결정 조회 (병렬) → 리포트 작성 → 과거 결정과 비교
 * /analyze/stream(SSE)이 노드가 끝날 때마다 알려 주므로, 각 단계는 실제로 끝난 시점에 완료로 바뀐다.
 * 펀더멘털은 서브그래프 안 단계(웹 검색 → 관련성 검사 → 재검색 …)까지 보여준다.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** 'running': 진행 중, 'done': 리포트 받음 */
  phase: 'running' | 'done'
  elapsed: number
  /** 응답에 과거 결정 비교가 포함됐는지 (done일 때만 의미 있음) */
  compared: boolean | null
  /** 끝난 노드 → 끝난 시각(초) */
  finished: Record<string, number>
  /** 펀더멘털 서브그래프에서 마지막으로 끝난 단계 */
  fundStep: string | null
  retries: number
  /** 과거 결정이 있는지 (past_decision 노드가 끝나면 알 수 있음) */
  hasPast: boolean | null
}>()

type Status = 'running' | 'waiting' | 'done' | 'skipped'

interface Step {
  key: string
  label: string
  detail: string
  status: Status
  at?: number
}

/** 서브그래프 단계가 끝났을 때, 다음에 무엇을 하는 중인지 */
const NEXT_OF: Record<string, string> = {
  search_documents: '웹 검색 결과 기다리는 중',
  search_web: '문서 합치는 중',
  unify_documents: '자료가 충분한지 검사 중',
  relevance_check: '요약 작성 중',
  query_rewrite: '새 검색어로 다시 검색 중',
  fundamental_summary: '요약 정리 중',
}

const steps = computed<{ parallel: Step[]; serial: Step[] }>(() => {
  const f = props.finished
  const all = props.phase === 'done'
  const st = (key: string, ready = true): Status => (key in f || all ? 'done' : ready ? 'running' : 'waiting')

  let fundDetail = '사업보고서·웹 문서 검색'
  if (!('fundamental' in f) && props.fundStep) {
    fundDetail = NEXT_OF[props.fundStep] ?? fundDetail
    if (props.retries) fundDetail += ` · 재검색 ${props.retries}회`
  } else if ('fundamental' in f && props.retries) {
    fundDetail = `자료 부족으로 재검색 ${props.retries}회 후 요약`
  }

  const reportReady = 'fundamental' in f && 'quant' in f
  const noPast = props.hasPast === false || (all && props.compared === false)
  let compare: Status = 'waiting'
  if ('new_vs_old' in f || (all && props.compared)) compare = 'done'
  else if (noPast) compare = 'skipped'
  else if ('old_exist' in f) compare = 'running'

  return {
    parallel: [
      { key: 'fundamental', label: '펀더멘털', detail: fundDetail, status: st('fundamental'), at: f.fundamental },
      { key: 'quant', label: '퀀트 지표', detail: '밸류에이션·컨센서스 수집', status: st('quant'), at: f.quant },
      {
        key: 'past_decision',
        label: '과거 결정',
        detail: props.hasPast === null ? '같은 종목의 지난 기록 조회' : props.hasPast ? '지난 결정 찾음' : '지난 결정 없음',
        status: st('past_decision'),
        at: f.past_decision,
      },
    ],
    serial: [
      {
        key: 'write_report',
        label: '리포트 작성',
        detail: 'verify' in f ? '독립 분석 + 숫자 검증 완료' : '과거 판단을 보지 않고 독립 분석',
        status: st('verify' in f ? 'verify' : 'write_report', reportReady),
        at: f.verify ?? f.write_report,
      },
      {
        key: 'compare',
        label: '과거 결정과 비교',
        detail: compare === 'skipped' ? '지난 결정이 없어 건너뜀' : '철회 조건·확인 필요 항목 점검',
        status: compare,
        at: f.new_vs_old,
      },
    ],
  }
})

const STATUS_TEXT: Record<Status, string> = {
  running: '진행 중',
  waiting: '대기',
  done: '완료',
  skipped: '건너뜀',
}

function stateText(s: Step) {
  return s.status === 'done' && s.at !== undefined ? `${s.at.toFixed(1)}초` : STATUS_TEXT[s.status]
}
</script>

<template>
  <div class="progress" role="status" aria-live="polite">
    <div class="flow">
      <ol class="parallel" aria-label="동시에 진행되는 분석">
        <li v-for="s in steps.parallel" :key="s.key" :class="['step', s.status]" >
          <span class="mark" aria-hidden="true" />
          <span class="text">
            <b>{{ s.label }}</b>
            <small>{{ s.detail }}</small>
          </span>
          <span class="state num">{{ stateText(s) }}</span>
        </li>
      </ol>
      <div class="join" aria-hidden="true" />
      <ol class="serial" aria-label="이어서 진행되는 단계">
        <li v-for="s in steps.serial" :key="s.key" :class="['step', s.status]" >
          <span class="mark" aria-hidden="true" />
          <span class="text">
            <b>{{ s.label }}</b>
            <small>{{ s.detail }}</small>
          </span>
          <span class="state num">{{ stateText(s) }}</span>
        </li>
      </ol>
    </div>
    <p class="clock">
      <span class="num">{{ elapsed }}</span>초 경과
      <span v-if="phase === 'running'" class="note">보통 수십 초 걸려요</span>
    </p>
  </div>
</template>

<style scoped>
.progress {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--rule);
}
.flow {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr);
  align-items: center;
}
@media (max-width: 640px) {
  .flow {
    grid-template-columns: 1fr;
  }
  .join {
    height: 20px;
    width: 0;
    margin-left: 7px;
    border-left: 1px solid var(--rule-strong);
    border-top: none !important;
    border-bottom: none !important;
    border-right: none !important;
  }
}
ol {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
/* 병렬 세 갈래가 한 점으로 모이는 괄호 */
.join {
  align-self: stretch;
  margin: 18px 0;
  border: 1px solid var(--rule-strong);
  border-left: none;
  border-radius: 0 6px 6px 0;
}
.serial {
  padding-left: 12px;
}
@media (max-width: 640px) {
  .serial {
    padding-left: 0;
  }
}
.step {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
}
.text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.text b {
  font-size: var(--t-md);
  font-weight: 600;
}
.text small {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.state {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.mark {
  position: relative;
  width: 14px;
  height: 14px;
  border: 1.5px solid var(--rule-strong);
  border-radius: 50%;
}
.step.running .mark {
  border-color: var(--accent);
  border-right-color: transparent;
  animation: spin 0.9s linear infinite;
}
.step.running .state {
  color: var(--accent);
}
.step.waiting {
  opacity: 0.55;
}
.step.done .mark {
  border-color: var(--up);
  background: var(--up);
  animation: pop 0.3s ease both;
}
.step.done .mark::after {
  content: '';
  position: absolute;
  left: 3.5px;
  top: 1px;
  width: 3.5px;
  height: 7px;
  border: solid var(--sheet);
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}
.step.done .state {
  color: var(--up);
}
.step.skipped .mark {
  border-style: dashed;
}
.step.skipped {
  opacity: 0.6;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes pop {
  0% {
    transform: scale(0.4);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
.clock {
  margin: 14px 0 0;
  font-size: var(--t-sm);
  color: var(--ink-soft);
}
.note {
  margin-left: 10px;
  color: var(--ink-faint);
}
</style>
