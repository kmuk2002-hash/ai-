<script setup lang="ts">
/**
 * 상단 알림. 결정을 내린 종목을 다시 분석했을 때 '과거 결정 대비' 점검 결과가 생기면 여기에 쌓인다.
 * 누르면 그 결정을 내린 원래 리포트로 이동하고 읽음 처리한다.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useNotices } from '../composables/notices'
import { ACTION_LABEL, CATEGORY_LABEL } from '../types'
import type { DecisionNotice } from '../types'
import { shortDate } from '../lib/format'

const router = useRouter()
const { notices, unread, markRead, isRead } = useNotices()
const open = ref(false)
const root = ref<HTMLElement | null>(null)

const hasAlert = computed(() => unread.value.some((n) => n.level === 'alert'))

function headline(n: DecisionNotice) {
  if (n.level === 'alert') return '철회 조건이 충족됐어요'
  if (n.triggered.length) return `${CATEGORY_LABEL[n.triggered[0].category]}에 변화가 있어요`
  return '다시 점검한 결과가 도착했어요'
}

function detail(n: DecisionNotice) {
  const c = n.triggered.find((x) => x.category === 'thesis_breaker') ?? n.triggered[0]
  return c ? c.evidence : n.summary.split('\n')[0]
}

function go(n: DecisionNotice) {
  markRead(n.id)
  open.value = false
  router.push({ name: 'report', params: { id: n.decision_report_id }, hash: '#since' })
}

function onDoc(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}
onMounted(() => {
  document.addEventListener('mousedown', onDoc)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDoc)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="root" class="bell-wrap">
    <button
      type="button"
      class="bell"
      :aria-expanded="open"
      aria-haspopup="true"
      :aria-label="`결정 이후 소식 ${unread.length}건 읽지 않음`"
      @click="open = !open"
    >
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
        <path d="M10 2.5a5 5 0 0 0-5 5v3.2L3.6 13.4a.8.8 0 0 0 .7 1.1h11.4a.8.8 0 0 0 .7-1.1L15 10.7V7.5a5 5 0 0 0-5-5Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
        <path d="M8 16.2a2 2 0 0 0 4 0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
      <span v-if="unread.length" :class="['count', 'num', { alert: hasAlert }]">{{ unread.length }}</span>
    </button>

    <Transition name="drop">
      <div v-if="open" class="panel" role="dialog" aria-label="결정 이후 소식">
        <div class="panel-head">
          <b>결정 이후 소식</b>
          <button v-if="unread.length" type="button" class="link-btn" @click="markRead(...unread.map((n) => n.id))">
            모두 읽음
          </button>
        </div>
        <p v-if="!notices.length" class="empty">
          결정을 기록한 종목을 다시 분석하면, 그때 정한 철회 조건과 확인할 항목을 점검한 결과가 여기에 와요.
        </p>
        <ul v-else>
          <li v-for="n in notices" :key="n.id">
            <button type="button" :class="['item', n.level, { read: isRead(n.id) }]" @click="go(n)">
              <span class="item-top">
                <span class="tk num">{{ n.ticker }}</span>
                <span class="act">{{ ACTION_LABEL[n.action] }} 결정 이후</span>
                <span class="when">{{ shortDate(n.created_at) }} 재분석</span>
              </span>
              <span class="item-head">{{ headline(n) }}</span>
              <span class="item-body">{{ detail(n) }}</span>
            </button>
          </li>
        </ul>
        <RouterLink class="panel-foot" :to="{ name: 'library' }" @click="open = false">기록 보관함에서 모아 보기</RouterLink>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.bell-wrap {
  position: relative;
}
.bell {
  position: relative;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  color: var(--ink-soft);
  background: none;
  border: 1px solid transparent;
  border-radius: 50%;
  cursor: pointer;
}
.bell:hover {
  color: var(--ink);
  background: var(--accent-wash);
}
.count {
  position: absolute;
  top: 2px;
  right: 0;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  font-size: 11px;
  line-height: 17px;
  font-weight: 500;
  color: #fff;
  background: var(--accent);
  border-radius: 9px;
  box-shadow: 0 0 0 2px var(--paper);
}
.count.alert {
  background: var(--down);
}
.panel {
  position: absolute;
  top: calc(100% + 8px);
  right: -8px;
  width: min(380px, calc(100vw - 24px));
  max-height: min(70vh, 560px);
  display: flex;
  flex-direction: column;
  background: var(--sheet);
  border-radius: 8px;
  box-shadow: var(--shadow-slip), 0 0 0 1px var(--rule);
  overflow: hidden;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--rule);
}
.panel-head b {
  font-size: var(--t-md);
}
.link-btn {
  padding: 0;
  font: inherit;
  font-size: var(--t-sm);
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
}
.empty {
  margin: 0;
  padding: 18px 16px;
  font-size: var(--t-sm);
  color: var(--ink-faint);
  line-height: 1.7;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
}
.item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 12px 16px 12px 14px;
  text-align: left;
  font: inherit;
  color: var(--ink);
  background: none;
  border: none;
  border-left: 3px solid var(--accent);
  border-bottom: 1px solid var(--rule);
  cursor: pointer;
}
.item.alert {
  border-left-color: var(--down);
}
.item:hover {
  background: var(--sheet-alt);
}
.item.read {
  border-left-color: var(--rule);
  opacity: 0.7;
}
.item-top {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: var(--t-xs);
  color: var(--ink-faint);
}
.tk {
  font-size: var(--t-sm);
  font-weight: 500;
  color: var(--ink);
}
.when {
  margin-left: auto;
}
.item-head {
  font-weight: 600;
  font-size: var(--t-md);
}
.item.alert:not(.read) .item-head {
  color: var(--down);
}
.item-body {
  font-size: var(--t-sm);
  color: var(--ink-soft);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.panel-foot {
  padding: 11px 16px;
  font-size: var(--t-sm);
  text-align: center;
  text-decoration: none;
  background: var(--sheet-alt);
}
.drop-enter-active,
.drop-leave-active {
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
