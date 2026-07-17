<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

interface Particle {
  x: number
  y: number
  size: number
  speedX: number
  speedY: number
  opacity: number
  color: string
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
const particles = ref<Particle[]>([])
const mouseX = ref(0)
const mouseY = ref(0)

const colors = ['#3b82f6', '#06b6d4', '#8b5cf6', '#10b981']

function createParticle(width: number, height: number): Particle {
  return {
    x: Math.random() * width,
    y: Math.random() * height,
    size: Math.random() * 2 + 0.5,
    speedX: (Math.random() - 0.5) * 0.5,
    speedY: (Math.random() - 0.5) * 0.5,
    opacity: Math.random() * 0.5 + 0.1,
    color: colors[Math.floor(Math.random() * colors.length)],
  }
}

function initParticles() {
  const canvas = canvasRef.value
  if (!canvas) return

  const width = canvas.width
  const height = canvas.height

  particles.value = []
  const particleCount = Math.floor((width * height) / 15000)

  for (let i = 0; i < particleCount; i++) {
    particles.value.push(createParticle(width, height))
  }
}

function animate() {
  const canvas = canvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (const particle of particles.value) {
    // Update position
    particle.x += particle.speedX
    particle.y += particle.speedY

    // Mouse interaction
    const dx = mouseX.value - particle.x
    const dy = mouseY.value - particle.y
    const distance = Math.sqrt(dx * dx + dy * dy)

    if (distance < 150) {
      const force = (150 - distance) / 150
      particle.speedX -= (dx / distance) * force * 0.02
      particle.speedY -= (dy / distance) * force * 0.02
    }

    // Wrap around
    if (particle.x < 0) particle.x = canvas.width
    if (particle.x > canvas.width) particle.x = 0
    if (particle.y < 0) particle.y = canvas.height
    if (particle.y > canvas.height) particle.y = 0

    // Draw particle
    ctx.beginPath()
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2)
    ctx.fillStyle = particle.color
    ctx.globalAlpha = particle.opacity
    ctx.fill()

    // Draw connections
    for (const other of particles.value) {
      if (particle === other) continue

      const dx2 = particle.x - other.x
      const dy2 = particle.y - other.y
      const dist = Math.sqrt(dx2 * dx2 + dy2 * dy2)

      if (dist < 100) {
        ctx.beginPath()
        ctx.moveTo(particle.x, particle.y)
        ctx.lineTo(other.x, other.y)
        ctx.strokeStyle = particle.color
        ctx.globalAlpha = (1 - dist / 100) * 0.15
        ctx.lineWidth = 0.5
        ctx.stroke()
      }
    }
  }

  ctx.globalAlpha = 1
  requestAnimationFrame(animate)
}

function handleResize() {
  const canvas = canvasRef.value
  if (!canvas) return

  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  initParticles()
}

function handleMouseMove(e: MouseEvent) {
  mouseX.value = e.clientX
  mouseY.value = e.clientY
}

onMounted(() => {
  handleResize()
  animate()
  window.addEventListener('resize', handleResize)
  window.addEventListener('mousemove', handleMouseMove)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('mousemove', handleMouseMove)
})
</script>

<template>
  <canvas
    ref="canvasRef"
    class="absolute inset-0 w-full h-full pointer-events-none"
    style="background: radial-gradient(ellipse at center, rgba(59, 130, 246, 0.03) 0%, transparent 70%);"
  />
</template>
