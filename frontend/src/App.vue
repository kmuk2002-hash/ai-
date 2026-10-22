<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { USE_MOCK } from './api/client'
import { mockApi } from './mocks/server'
import MarketBackdrop from './components/MarketBackdrop.vue'
import NoticeBell from './components/NoticeBell.vue'
import { useNotices } from './composables/notices'

const route = useRoute()
const { refresh } = useNotices()

// 처음 열 때, 그리고 화면을 옮길 때마다 알림을 새로 받는다 (새 분석이 끝나면 바로 반영)
onMounted(refresh)
watch(() => route.fullPath, refresh)

function resetMock() {
  if (!window.confirm('목업 데이터(리포트·하이라이트·결정)를 처음 상태로 되돌릴까요?')) return
  mockApi.reset()
  window.location.assign('/')
}
</script>

<template>
  <MarketBackdrop />
  <header class="topbar">
    <div class="topbar-inner">
      <RouterLink to="/" class="brand">
        <svg class="brand-mark" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <rect x="0.75" y="0.75" width="22.5" height="22.5" rx="6" fill="var(--accent)" />
          <path d="M5 15.5 9 11l3 3 6.5-7" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        투자 노트
      </RouterLink>
      <nav aria-label="주 메뉴">
        <RouterLink to="/">분석</RouterLink>
        <RouterLink :to="{ name: 'library' }">기록 보관함</RouterLink>
      </nav>
      <div class="right">
        <div v-if="USE_MOCK" class="mock">
          <span class="mock-badge" title="백엔드 없이 가짜 데이터로 동작하는 중">목업 데이터</span>
          <button type="button" class="link-btn" @click="resetMock">초기화</button>
        </div>
        <NoticeBell />
      </div>
    </div>
  </header>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--rule);
}
.topbar-inner {
  display: flex;
  align-items: center;
  gap: 28px;
  max-width: 1240px;
  height: 56px;
  margin: 0 auto;
  padding: 0 20px;
}
@media (max-width: 600px) {
  .topbar-inner {
    gap: 16px;
    padding: 0 14px;
  }
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  text-decoration: none;
  white-space: nowrap;
  letter-spacing: -0.01em;
}
.brand-mark {
  flex: none;
}
nav {
  display: flex;
  gap: 22px;
}
nav a {
  font-size: var(--t-md);
  color: var(--ink-soft);
  text-decoration: none;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
}
nav a.router-link-exact-active {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
.right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}
.mock {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--t-sm);
}
.mock-badge {
  padding: 1px 8px;
  color: var(--hold);
  border: 1px dashed currentColor;
  border-radius: 2px;
  white-space: nowrap;
}
.link-btn {
  padding: 0;
  font: inherit;
  color: var(--ink-soft);
  background: none;
  border: none;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  white-space: nowrap;
}
@media (max-width: 600px) {
  .mock {
    display: none;
  }
}
</style>
