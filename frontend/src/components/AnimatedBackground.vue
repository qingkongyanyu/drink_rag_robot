<template>
  <div class="abg" aria-hidden="true">
    <div class="abg-blob abg-blob-1"></div>
    <div class="abg-blob abg-blob-2"></div>
    <div class="abg-blob abg-blob-3"></div>
    <div class="abg-aurora abg-aurora-1"></div>
    <div class="abg-aurora abg-aurora-2"></div>
    <div class="abg-grid"></div>
    <canvas ref="canvas" class="abg-canvas"></canvas>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const canvas = ref(null)
let ctx, raf, particles = []
const W = () => window.innerWidth
const H = () => window.innerHeight

class P {
  constructor() {
    this.reset(true)
  }
  reset(init = false) {
    this.x = Math.random() * W()
    this.y = Math.random() * H()
    this.r = Math.random() * 1.8 + 0.6
    this.sx = (Math.random() - 0.5) * 0.5
    this.sy = (Math.random() - 0.5) * 0.5
    this.o = Math.random() * 0.4 + 0.15
    // 颜色在 青 / 绿 / 紫 之间随机
    const palette = ['56,189,248', '52,211,153', '139,92,246']
    this.color = palette[Math.floor(Math.random() * palette.length)]
    if (!init) {
      this.r = Math.random() * 1.8 + 0.6
    }
  }
  step() {
    this.x += this.sx
    this.y += this.sy
    if (this.x < -10) this.x = W() + 10
    if (this.x > W() + 10) this.x = -10
    if (this.y < -10) this.y = H() + 10
    if (this.y > H() + 10) this.y = -10
  }
}

function resize() {
  const el = canvas.value
  el.width = W()
  el.height = H()
}

function draw() {
  ctx.clearRect(0, 0, W(), H())
  const link = 110
  particles.forEach((p) => {
    p.step()
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${p.color}, ${p.o})`
    ctx.fill()
  })
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const a = particles[i], b = particles[j]
      const dx = a.x - b.x, dy = a.y - b.y
      const d = Math.sqrt(dx * dx + dy * dy)
      if (d < link) {
        ctx.beginPath()
        ctx.moveTo(a.x, a.y)
        ctx.lineTo(b.x, b.y)
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.2 * (1 - d / link)})`
        ctx.lineWidth = 0.5
        ctx.stroke()
      }
    }
  }
  raf = requestAnimationFrame(draw)
}

function init() {
  const el = canvas.value
  ctx = el.getContext('2d')
  resize()
  const count = Math.min(90, Math.floor((W() * H()) / 18000))
  particles = Array.from({ length: count }, () => new P())
  window.addEventListener('resize', resize)
  draw()
}

onMounted(init)
onUnmounted(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
})
</script>

<style scoped>
.abg { position: fixed; inset: 0; z-index: 0; overflow: hidden;
  background:
    radial-gradient(1200px 700px at 15% -10%, rgba(14,165,233,.18), transparent 60%),
    radial-gradient(1100px 600px at 90% 110%, rgba(52,211,153,.14), transparent 60%),
    radial-gradient(900px 600px at 70% 20%, rgba(139,92,246,.10), transparent 60%),
    linear-gradient(135deg, var(--bg-0), var(--bg-1) 55%, var(--bg-2));
  transition: background 0.5s ease;
}
.abg-canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.abg-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(56,189,248,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56,189,248,.05) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(ellipse 80% 60% at 50% 40%, black 30%, transparent 75%);
}
.abg-blob { position: absolute; border-radius: 50%; filter: blur(90px); opacity: .5; animation: blob-move 22s ease-in-out infinite; }
.abg-blob-1 { width: 480px; height: 480px; left: -120px; top: -80px; background: rgba(14,165,233,.32); }
.abg-blob-2 { width: 420px; height: 420px; right: -100px; bottom: -60px; background: rgba(52,211,153,.24); animation-delay: -7s; }
.abg-blob-3 { width: 360px; height: 360px; left: 40%; top: 55%; background: rgba(139,92,246,.18); animation-delay: -14s; }

/* 极光光带：柔和流动，提升高级感 */
.abg-aurora {
  position: absolute;
  height: 240px;
  filter: blur(70px);
  opacity: .35;
  border-radius: 50%;
  animation: aurora-drift 16s ease-in-out infinite;
  will-change: transform, opacity;
}
.abg-aurora-1 {
  left: -20%; right: -20%; top: 8%;
  background: linear-gradient(90deg, transparent, rgba(14,165,233,.5) 30%, rgba(99,102,241,.45) 60%, transparent);
}
.abg-aurora-2 {
  left: -15%; right: -15%; bottom: 4%;
  background: linear-gradient(90deg, transparent, rgba(52,211,153,.4) 35%, rgba(139,92,246,.35) 70%, transparent);
  animation-delay: -8s;
  animation-duration: 20s;
}
</style>
