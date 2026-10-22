<script setup lang="ts">
/** 하이라이트 저장 팝오버: 형광펜 색(태그) 4개 중 하나 + 메모 */
import { nextTick, onMounted, ref } from 'vue'
import type { HighlightSpan, HighlightTag } from '../types'
import { FIELD_LABEL, TAG_META } from '../types'

const props = defineProps<{
  x: number
  y: number
  spans: HighlightSpan[]
  saving?: boolean
}>()

const emit = defineEmits<{
  save: [payload: { tag: HighlightTag; comment: string | null }]
  cancel: []
}>()

const tags = Object.keys(TAG_META) as HighlightTag[]
const tag = ref<HighlightTag>('to_verify')
const comment = ref('')
const root = ref<HTMLElement | null>(null)

const TAG_HINT: Record<HighlightTag, string> = {
  support: '매수 근거로 삼을 내용',
  concern: '리스크로 인정하는 내용',
  to_verify: '다음 실적에서 확인할 내용',
  disagree: '동의하지 않는 분석',
}

function save() {
  emit('save', { tag: tag.value, comment: comment.value.trim() || null })
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
}

const preview = props.spans.map((s) => s.quoted_text).join(' … ')
const fields = [...new Set(props.spans.map((s) => FIELD_LABEL[s.field]))].join(', ')

onMounted(async () => {
  await nextTick()
  // 키보드 사용자를 위해 선택된 태그 버튼에 포커스 (스크롤 이동 없이)
  root.value?.querySelector<HTMLButtonElement>('.tag-btn.selected')?.focus({ preventScroll: true })
})
</script>

<template>
  <div
    ref="root"
    class="popover"
    :style="{ left: `${x}px`, top: `${y}px` }"
    role="dialog"
    aria-label="하이라이트 저장"
    @mousedown.stop
    @mouseup.stop
    @keydown="onKey"
  >
    <p class="preview" :title="preview">{{ preview }}</p>
    <p class="fields">{{ spans.length > 1 ? `${fields}, ${spans.length}개 섹션에 걸침` : fields }}</p>

    <div class="tags" role="radiogroup" aria-label="태그">
      <button
        v-for="t in tags"
        :key="t"
        type="button"
        role="radio"
        :class="['tag-btn', `tag-${t}`, { selected: tag === t }]"
        :aria-checked="tag === t"
        :title="TAG_HINT[t]"
        @click="tag = t"
      >
        <span class="swatch" aria-hidden="true" />
        {{ TAG_META[t].label }}
      </button>
    </div>

    <textarea v-model="comment" rows="2" placeholder="메모 (선택)" @keydown.meta.enter="save" @keydown.ctrl.enter="save" />

    <div class="actions">
      <button type="button" class="btn ghost" @click="emit('cancel')">취소</button>
      <button type="button" class="btn primary" :disabled="saving" @click="save">
        {{ saving ? '저장 중' : '형광펜 저장' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.popover {
  position: absolute;
  z-index: 50;
  width: min(304px, calc(100vw - 16px));
  padding: 14px 14px 12px;
  background: var(--sheet);
  border: 1px solid var(--rule-strong);
  border-top: 3px solid var(--ink);
  border-radius: 2px;
  box-shadow: var(--shadow-slip);
}
.preview {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-md);
  line-height: 1.55;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.fields {
  margin: 4px 0 12px;
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.tags {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 6px;
}
.tag-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  font: inherit;
  font-size: var(--t-sm);
  color: var(--ink);
  text-align: left;
  background: transparent;
  border: 1px solid var(--rule);
  border-radius: 2px;
  cursor: pointer;
  transition: border-color 0.12s ease, background-color 0.12s ease;
}
.tag-btn:hover {
  border-color: var(--rule-strong);
}
.tag-btn.selected {
  border-color: var(--ink);
  background: var(--sheet-alt);
  font-weight: 600;
}
.swatch {
  width: 22px;
  height: 11px;
  border-radius: 6px 2px 5px 3px / 3px 6px 2px 5px;
}
.tag-support .swatch { background: var(--m-support); }
.tag-concern .swatch { background: var(--m-concern); }
.tag-to_verify .swatch { background: var(--m-to_verify); }
.tag-disagree .swatch { background: var(--m-disagree); }
textarea {
  resize: vertical;
  font-size: var(--t-sm);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 12px;
}
.actions .btn {
  padding: 7px 12px;
  font-size: var(--t-sm);
}
</style>
