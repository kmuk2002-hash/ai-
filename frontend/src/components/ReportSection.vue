<script setup lang="ts">
/**
 * 리포트 섹션 1개. 왼쪽 여백 칸에 섹션 이름, 붉은 여백선 오른쪽에 원문.
 * 원문은 그대로(pre-wrap) 렌더링하고, 저장된 하이라이트를 형광펜 자국으로 표시한다.
 * .section-text 안에는 원문 외의 텍스트가 들어가면 안 된다 (offset 계산의 전제).
 */
import { computed } from 'vue'
import type { HighlightGroup, ReportField } from '../types'
import { buildSegments } from '../composables/useHighlight'

const props = defineProps<{
  field: ReportField
  title: string
  text: string
  groups: HighlightGroup[]
  activeGroupId: string | null
  /** 방금 저장한 그룹: 형광펜이 그어지는 애니메이션 */
  freshGroupId?: string | null
}>()

const emit = defineEmits<{ select: [groupId: string] }>()

const segments = computed(() => buildSegments(props.text, props.field, props.groups))

function segClass(seg: { tag: string | null; groupIds: string[] }) {
  return [
    'seg',
    seg.tag && `hl hl-${seg.tag}`,
    seg.groupIds.length > 1 && 'hl-overlap',
    props.activeGroupId && seg.groupIds.includes(props.activeGroupId) && 'hl-active',
    props.freshGroupId && seg.groupIds.includes(props.freshGroupId) && 'hl-fresh',
  ]
}

function onSegmentClick(groupIds: string[]) {
  if (!groupIds.length) return
  // 텍스트를 드래그 중이면 클릭으로 처리하지 않음
  const sel = window.getSelection()
  if (sel && !sel.isCollapsed) return
  // 겹친 경우: 현재 선택된 그룹 다음 것으로 순환
  const idx = props.activeGroupId ? groupIds.indexOf(props.activeGroupId) : -1
  emit('select', groupIds[(idx + 1) % groupIds.length] ?? groupIds[groupIds.length - 1])
}
</script>

<template>
  <section class="report-section">
    <h3 class="section-title">{{ title }}</h3>
    <div class="section-text" :data-field="field"><span v-for="seg in segments" :key="seg.start" :class="segClass(seg)" :data-groups="seg.groupIds.length ? seg.groupIds.join(' ') : undefined" :data-start="seg.start" @click="onSegmentClick(seg.groupIds)">{{ seg.text }}</span></div>
  </section>
</template>

<style scoped>
.report-section {
  display: grid;
  grid-template-columns: var(--margin-col, 132px) minmax(0, 1fr);
  column-gap: 0;
}
.section-title {
  margin: 0;
  padding: 3px 20px 0 0;
  font-family: var(--font-sans);
  font-size: var(--t-sm);
  font-weight: 600;
  line-height: 1.5;
  color: var(--ink-soft);
  text-align: right;
}
.section-text {
  padding: 0 0 0 24px;
  border-left: 1px solid var(--margin-rule);
  max-width: 68ch;
  white-space: pre-wrap;
  word-break: keep-all;
  overflow-wrap: anywhere;
  font-family: var(--font-serif);
  font-size: var(--t-body);
  font-weight: 500;
  line-height: 1.9;
  color: var(--ink);
}
@media (max-width: 640px) {
  .report-section {
    grid-template-columns: 1fr;
  }
  .section-title {
    padding: 0 0 6px 16px;
    text-align: left;
  }
  .section-text {
    padding-left: 15px;
    font-size: 16px;
  }
}

/* ── 형광펜 ─────────────────────────────────────────
   양 끝이 살짝 옅고 모서리가 고르지 않은 마커 자국.
   좌우 padding은 음수 margin으로 상쇄해 글자 배치를 바꾸지 않는다. */
.hl {
  --m: transparent;
  padding: 0.08em 0.18em;
  margin: 0 -0.18em;
  border-radius: 0.5em 0.18em 0.42em 0.22em / 0.32em 0.5em 0.24em 0.46em;
  background-image: linear-gradient(
    96deg,
    color-mix(in srgb, var(--m) 55%, transparent) 0%,
    var(--m) 4%,
    var(--m) 95%,
    color-mix(in srgb, var(--m) 60%, transparent) 100%
  );
  background-repeat: no-repeat;
  background-size: 100% 100%;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  cursor: pointer;
}
.hl-support { --m: var(--m-support); }
.hl-concern { --m: var(--m-concern); }
.hl-to_verify { --m: var(--m-to_verify); }
.hl-disagree { --m: var(--m-disagree); }

/* 겹친 부분: 한 번 더 그은 것처럼 진하게 */
.hl-overlap {
  background-color: color-mix(in srgb, var(--m) 70%, transparent);
}

/* 선택된 하이라이트: 잉크 밑줄 */
.hl-active {
  text-decoration: underline 2px var(--accent);
  text-underline-offset: 0.28em;
}

/* 방금 저장한 하이라이트: 왼쪽에서 오른쪽으로 그어짐 */
.hl-fresh {
  animation: marker-draw 0.55s cubic-bezier(0.3, 0.7, 0.2, 1) both;
}
@keyframes marker-draw {
  from {
    background-size: 0% 100%;
  }
  to {
    background-size: 100% 100%;
  }
}
</style>
