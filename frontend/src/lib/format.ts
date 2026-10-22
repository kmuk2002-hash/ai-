/** 화면 공용 날짜 표기 */
const WD = ['일', '월', '화', '수', '목', '금', '토']

export function dayKey(iso: string): string {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 2026-10-22 → "10월 22일 (목)", 올해가 아니면 연도 포함 */
export function dayLabel(key: string): string {
  const [y, m, d] = key.split('-').map(Number)
  const wd = WD[new Date(y, m - 1, d).getDay()]
  const year = y === new Date().getFullYear() ? '' : `${y}년 `
  return `${year}${m}월 ${d}일 (${wd})`
}

/** ISO → "10월 8일" */
export function shortDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getMonth() + 1}월 ${d.getDate()}일`
}
