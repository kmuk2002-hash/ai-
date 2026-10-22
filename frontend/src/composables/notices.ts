/**
 * 결정 이후 소식(알림).
 *  - 목록은 서버(GET /notifications)가 계산한다. 목업은 toNotice()로 같은 규칙을 따른다.
 *  - "읽음" 표시는 이 브라우저에만 저장한다(localStorage). 기기 간 동기화는 하지 않는다.
 */
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { DecisionNotice } from '../types'
export { toNotice } from '../lib/notice'

const READ_KEY = 'invest-notice-read-v1'

function loadRead(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(READ_KEY) ?? '[]') as string[])
  } catch {
    return new Set()
  }
}

const notices = ref<DecisionNotice[]>([])
const read = ref<Set<string>>(loadRead())
const loaded = ref(false)

function saveRead() {
  try {
    localStorage.setItem(READ_KEY, JSON.stringify([...read.value]))
  } catch {
    /* 저장소를 못 쓰면 이번 방문 동안만 기억 */
  }
}

export function useNotices() {
  const unread = computed(() => notices.value.filter((n) => !read.value.has(n.id)))

  async function refresh() {
    try {
      notices.value = await api.listNotifications()
    } catch {
      /* 알림은 없어도 화면은 동작 */
    } finally {
      loaded.value = true
    }
  }

  function markRead(...ids: string[]) {
    ids.forEach((id) => read.value.add(id))
    read.value = new Set(read.value)
    saveRead()
  }

  /** 이 리포트로 내린 결정에 붙은 알림 */
  function forReport(reportId: string) {
    return notices.value.filter((n) => n.decision_report_id === reportId)
  }

  const isRead = (id: string) => read.value.has(id)

  return { notices, unread, loaded, refresh, markRead, forReport, isRead }
}
