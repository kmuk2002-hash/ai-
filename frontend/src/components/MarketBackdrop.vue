<script setup lang="ts">
/**
 * 배경 시세 차트. 가상의 종목 하나가 실시간으로 움직이는 것처럼 그린다(실제 데이터 아님).
 *  - 화면 아래쪽 띠에 가격선 + 옅은 면 + 거래량 막대. 본문(흰 시트) 뒤에 깔려 여백에서만 보인다.
 *  - 새 틱이 TICK_MS마다 하나씩 추가되고, 그 사이를 부드럽게 흘러가게 보간한다.
 *  - 움직임 줄이기 설정이면 한 번만 그리고 멈춘다. 탭이 안 보이면 그리지 않는다.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const canvas = ref<HTMLCanvasElement | null>(null)

const TICK_MS = 900
const POINTS = 90
const GREEN = '14, 143, 98'
const RED = '216, 68, 58'

// 평균으로 돌아가려는 성질이 있는 랜덤워크 (가격이 화면 밖으로 새지 않게)
let price = 184
const anchor = 184
const series: { p: number; v: number }[] = []
function nextTick() {
  const drift = (anchor - price) * 0.04
  const shock = (Math.random() - 0.5) * 2.6
  price = Math.max(120, price + drift + shock)
  series.push({ p: price, v: 0.25 + Math.random() * 0.75 })
  if (series.length > POINTS + 2) series.shift()
}
for (let i = 0; i < POINTS + 2; i++) nextTick()
const open = series[0].p

let raf = 0
let timer: number | undefined
let lastTick = performance.now()
let ctx: CanvasRenderingContext2D | null = null
let w = 0
let h = 0
const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function resize() {
  const c = canvas.value
  if (!c) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  w = window.innerWidth
  h = window.innerHeight
  c.width = Math.round(w * dpr)
  c.height = Math.round(h * dpr)
  c.style.width = `${w}px`
  c.style.height = `${h}px`
  ctx = c.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  if (reduced) draw(lastTick)
}

function draw(now: number) {
  if (!ctx) return
  const g = ctx
  g.clearRect(0, 0, w, h)

  // 차트 영역: 화면 아래 58% 띠
  const top = h * 0.42
  const bottom = h - 28
  const band = bottom - top
  const step = w / (POINTS - 1)
  const frac = Math.min((now - lastTick) / TICK_MS, 1)   // 다음 틱까지 흘러간 정도
  const shift = frac * step

  const ps = series.map((s) => s.p)
  const lo = Math.min(...ps) - 4
  const hi = Math.max(...ps) + 4
  const y = (p: number) => top + (1 - (p - lo) / (hi - lo)) * band * 0.78
  const x = (i: number) => i * step - shift

  // 가로 괘선
  g.strokeStyle = `rgba(${GREEN}, 0.06)`
  g.lineWidth = 1
  for (let gy = top; gy <= bottom; gy += 56) {
    g.beginPath()
    g.moveTo(0, Math.round(gy) + 0.5)
    g.lineTo(w, Math.round(gy) + 0.5)
    g.stroke()
  }

  // 거래량 막대
  const volBase = bottom
  series.forEach((s, i) => {
    const up = i > 0 && s.p >= series[i - 1].p
    g.fillStyle = `rgba(${up ? GREEN : RED}, 0.07)`
    const bh = s.v * band * 0.16
    g.fillRect(x(i) - step * 0.3, volBase - bh, step * 0.6, bh)
  })

  // 가격선 아래 면
  const grad = g.createLinearGradient(0, top, 0, bottom)
  grad.addColorStop(0, `rgba(${GREEN}, 0.13)`)
  grad.addColorStop(1, `rgba(${GREEN}, 0)`)
  g.beginPath()
  series.forEach((s, i) => (i ? g.lineTo(x(i), y(s.p)) : g.moveTo(x(i), y(s.p))))
  g.lineTo(x(series.length - 1), bottom)
  g.lineTo(x(0), bottom)
  g.closePath()
  g.fillStyle = grad
  g.fill()

  // 가격선
  g.beginPath()
  series.forEach((s, i) => (i ? g.lineTo(x(i), y(s.p)) : g.moveTo(x(i), y(s.p))))
  g.strokeStyle = `rgba(${GREEN}, 0.42)`
  g.lineWidth = 1.6
  g.lineJoin = 'round'
  g.stroke()

  // 시가 기준선 (점선)
  g.setLineDash([4, 6])
  g.strokeStyle = `rgba(20, 35, 28, 0.12)`
  g.beginPath()
  g.moveTo(0, y(open) + 0.5)
  g.lineTo(w, y(open) + 0.5)
  g.stroke()
  g.setLineDash([])

  // 마지막 가격 점 + 가격표
  const last = series[series.length - 1]
  const lx = x(series.length - 1)
  const ly = y(last.p)
  const chg = (last.p / open - 1) * 100
  const tone = chg >= 0 ? GREEN : RED
  const pulse = 0.5 + 0.5 * Math.sin(now / 320)
  g.fillStyle = `rgba(${tone}, ${0.12 + 0.12 * pulse})`
  g.beginPath()
  g.arc(lx, ly, 7 + 3 * pulse, 0, Math.PI * 2)
  g.fill()
  g.fillStyle = `rgba(${tone}, 0.8)`
  g.beginPath()
  g.arc(lx, ly, 3, 0, Math.PI * 2)
  g.fill()

  const label = `${last.p.toFixed(2)}  ${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`
  g.font = '500 12px "IBM Plex Mono", ui-monospace, monospace'
  const tw = g.measureText(label).width + 14
  const tx = Math.min(lx + 12, w - tw - 8)
  g.fillStyle = `rgba(${tone}, 0.12)`
  g.fillRect(tx, ly - 11, tw, 22)
  g.fillStyle = `rgba(${tone}, 0.75)`
  g.fillText(label, tx + 7, ly + 4)
}

function loop(now: number) {
  draw(now)
  raf = requestAnimationFrame(loop)
}

function start() {
  timer = window.setInterval(() => {
    nextTick()
    lastTick = performance.now()
  }, TICK_MS)
  raf = requestAnimationFrame(loop)
}
function stop() {
  cancelAnimationFrame(raf)
  window.clearInterval(timer)
}
function onVisibility() {
  if (document.hidden) stop()
  else start()
}

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
  if (reduced) return   // 정지 화면 한 장만 (resize에서 그림)
  document.addEventListener('visibilitychange', onVisibility)
  start()
})

onBeforeUnmount(() => {
  stop()
  window.removeEventListener('resize', resize)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <canvas ref="canvas" class="backdrop" aria-hidden="true" />
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
</style>
