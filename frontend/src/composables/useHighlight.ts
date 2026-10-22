/**
 * 하이라이트 핵심 로직
 *
 * 1) 선택 → 조각 계산 (computeSpans)
 *    - 리포트 본문의 각 섹션은 data-field 속성을 가진 블록(.section-text)으로 렌더링된다.
 *    - 브라우저 Selection의 범위가 걸친 블록마다, 그 섹션 원문 기준의 시작·끝 offset을 계산한다.
 *    - 블록 밖에서 시작하거나 끝나는 선택은 블록 경계로 잘라낸다.
 *
 * 2) 저장된 하이라이트 → 렌더링용 조각 (buildSegments)
 *    - 섹션 원문을 하이라이트 경계로 잘라, 각 조각이 어떤 그룹에 덮여 있는지 계산한다.
 *    - 겹친 하이라이트는 depth가 커져 더 진하게 표시된다.
 *
 * 전제: .section-text 블록 안의 텍스트는 섹션 원문과 글자 단위로 같아야 한다
 *       (마크다운 변환 없음, 블록 안에 원문 외의 텍스트 노드 없음).
 */
import { ref, type Ref } from 'vue'
import type { HighlightGroup, HighlightSpan, HighlightTag, ReportField } from '../types'

export const SECTION_SELECTOR = '.section-text[data-field]'

/** 블록 시작부터 (node, offset)까지의 글자 수 = 섹션 원문 기준 offset */
function offsetWithin(block: Element, node: Node, offset: number): number {
  const r = document.createRange()
  r.setStart(block, 0)
  r.setEnd(node, offset)
  return r.toString().length
}

function blockContains(block: Element, node: Node): boolean {
  return block === node || block.contains(node)
}

/** 선택 범위를 섹션별 조각으로 변환. rawTexts: field → 섹션 원문 */
export function computeSpans(
  range: Range,
  container: Element,
  rawTexts: Partial<Record<ReportField, string>>,
): HighlightSpan[] {
  const spans: HighlightSpan[] = []
  const blocks = container.querySelectorAll<HTMLElement>(SECTION_SELECTOR)

  blocks.forEach((block) => {
    const field = block.dataset.field as ReportField
    const raw = rawTexts[field]
    if (raw === undefined || !range.intersectsNode(block)) return

    let start = blockContains(block, range.startContainer)
      ? offsetWithin(block, range.startContainer, range.startOffset)
      : 0
    let end = blockContains(block, range.endContainer)
      ? offsetWithin(block, range.endContainer, range.endOffset)
      : raw.length

    start = Math.max(0, Math.min(start, raw.length))
    end = Math.max(0, Math.min(end, raw.length))

    // 앞뒤 공백·줄바꿈은 하이라이트에서 제외
    while (start < end && /\s/.test(raw[start])) start++
    while (end > start && /\s/.test(raw[end - 1])) end--

    if (end > start) {
      spans.push({ field, start_offset: start, end_offset: end, quoted_text: raw.slice(start, end) })
    }
  })

  return spans
}

export interface Segment {
  start: number
  end: number
  text: string
  /** 이 조각을 덮는 하이라이트 그룹 id (생성 순) */
  groupIds: string[]
  /** 가장 최근 그룹의 태그 (색상 결정) */
  tag: HighlightTag | null
}

/** 섹션 원문을 하이라이트 경계로 잘라 렌더링용 조각 목록을 만든다 */
export function buildSegments(text: string, field: ReportField, groups: HighlightGroup[]): Segment[] {
  const covers: { start: number; end: number; id: string; tag: HighlightTag }[] = []
  groups.forEach((g, i) => {
    const id = g.id ?? `local-${i}`
    g.spans
      .filter((s) => s.field === field)
      .forEach((s) => {
        const start = Math.max(0, Math.min(s.start_offset, text.length))
        const end = Math.max(0, Math.min(s.end_offset, text.length))
        if (end > start) covers.push({ start, end, id, tag: g.tag })
      })
  })

  const cuts = new Set<number>([0, text.length])
  covers.forEach((c) => {
    cuts.add(c.start)
    cuts.add(c.end)
  })
  const points = [...cuts].sort((a, b) => a - b)

  const segments: Segment[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]
    const b = points[i + 1]
    if (b <= a) continue
    const hit = covers.filter((c) => c.start <= a && c.end >= b)
    segments.push({
      start: a,
      end: b,
      text: text.slice(a, b),
      groupIds: hit.map((c) => c.id),
      tag: hit.length ? hit[hit.length - 1].tag : null,
    })
  }
  return segments
}

export interface PendingHighlight {
  spans: HighlightSpan[]
  /** 팝오버 위치 (문서 기준, position: absolute) */
  x: number
  y: number
}

/**
 * 컨테이너 안에서의 텍스트 선택을 감지해 pending(저장 대기 하이라이트)으로 만든다.
 * 컨테이너의 mouseup/keyup 이벤트에 onSelectionEnd를 연결해서 사용.
 */
export function useHighlight(
  containerRef: Ref<HTMLElement | null>,
  getRawTexts: () => Partial<Record<ReportField, string>>,
) {
  const pending = ref<PendingHighlight | null>(null)

  function onSelectionEnd() {
    const container = containerRef.value
    const sel = window.getSelection()
    if (!container || !sel || sel.rangeCount === 0 || sel.isCollapsed) return

    const range = sel.getRangeAt(0)
    const spans = computeSpans(range, container, getRawTexts())
    if (!spans.length) return

    // 문서 기준 좌표로 계산 → 스크롤해도 팝오버가 선택 영역 옆에 붙어 있음
    const rect = range.getBoundingClientRect()
    const width = Math.min(300, window.innerWidth - 16)
    const height = 240
    const x = window.scrollX + Math.min(Math.max(8, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 8)
    const fitsBelow = rect.bottom + 8 + height <= window.innerHeight
    const y = window.scrollY + (fitsBelow || rect.top - height - 8 < 0 ? rect.bottom + 8 : rect.top - height - 8)
    pending.value = { spans, x, y }
  }

  function clear() {
    pending.value = null
    window.getSelection()?.removeAllRanges()
  }

  return { pending, onSelectionEnd, clear }
}
