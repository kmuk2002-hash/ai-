<script setup lang="ts">
/** 리포트 여백에 남긴 주석 목록 (오른쪽 레일) */
import { nextTick, watch } from 'vue'
import type { HighlightGroup } from '../types'
import { FIELD_LABEL, TAG_META } from '../types'

const props = defineProps<{
  groups: HighlightGroup[]
  activeGroupId: string | null
}>()

const emit = defineEmits<{ select: [groupId: string] }>()

// 본문에서 하이라이트를 클릭하면 목록의 해당 항목으로 스크롤
watch(
  () => props.activeGroupId,
  async (id) => {
    if (!id) return
    await nextTick()
    document.querySelector(`[data-list-group="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="hl-list">
    <div v-if="!groups.length" class="empty">
      <span class="empty-stroke" aria-hidden="true" />
      <p>본문에서 중요한 문장을 드래그하면 형광펜과 메모가 여기에 모여요. 여러 섹션에 걸쳐 선택해도 돼요.</p>
    </div>
    <button
      v-for="g in groups"
      :key="g.id ?? ''"
      type="button"
      :data-list-group="g.id"
      :class="['hl-item', `tag-${g.tag}`, { active: g.id === activeGroupId }]"
      :aria-pressed="g.id === activeGroupId"
      @click="g.id && emit('select', g.id)"
    >
      <span class="tag">
        <span class="swatch" aria-hidden="true" />
        {{ TAG_META[g.tag].label }}
      </span>
      <span v-for="(s, i) in g.spans" :key="i" class="quote">
        <span class="quote-field">{{ FIELD_LABEL[s.field] }}</span>
        <span class="quote-text">{{ s.quoted_text }}</span>
      </span>
      <span v-if="g.comment" class="comment">{{ g.comment }}</span>
    </button>
  </div>
</template>

<style scoped>
.hl-list {
  display: flex;
  flex-direction: column;
  max-height: 440px;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
}
.empty {
  padding: 4px 0 8px;
}
.empty-stroke {
  display: block;
  width: 72px;
  height: 12px;
  margin-bottom: 10px;
  background: var(--m-to_verify);
  border-radius: 7px 2px 6px 3px / 3px 7px 2px 6px;
  opacity: 0.7;
}
.empty p {
  margin: 0;
  font-size: var(--t-sm);
  color: var(--ink-soft);
  line-height: 1.65;
}
.hl-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 12px 10px 12px 12px;
  text-align: left;
  font: inherit;
  color: var(--ink);
  background: transparent;
  border: none;
  border-top: 1px solid var(--rule);
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease;
}
.hl-item:first-of-type {
  border-top: none;
}
.hl-item:hover {
  background: var(--sheet-alt);
}
.hl-item.active {
  background: var(--accent-wash);
  border-left-color: var(--accent);
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--t-xs);
  font-weight: 600;
  color: var(--ink-soft);
}
.swatch {
  width: 18px;
  height: 9px;
  border-radius: 5px 2px 4px 2px / 2px 5px 2px 4px;
}
.tag-support .swatch { background: var(--m-support); }
.tag-concern .swatch { background: var(--m-concern); }
.tag-to_verify .swatch { background: var(--m-to_verify); }
.tag-disagree .swatch { background: var(--m-disagree); }
.quote {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.quote-field {
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.quote-text {
  font-family: var(--font-serif);
  font-size: var(--t-sm);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.comment {
  padding-left: 10px;
  font-size: var(--t-sm);
  color: var(--ink-soft);
  border-left: 1px solid var(--rule-strong);
  white-space: pre-wrap;
}
</style>
