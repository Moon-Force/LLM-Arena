<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import gsap from 'gsap'
import ParticleBackground from '@/components/ParticleBackground.vue'
import ModelCard from '@/components/ModelCard.vue'
import StatCard from '@/components/StatCard.vue'
import { useArenaStore } from '@/stores/arena'

const router = useRouter()
const store = useArenaStore()
const { t } = useI18n()

const heroRef = ref<HTMLElement | null>(null)
const statsRef = ref<HTMLElement | null>(null)
const modelsRef = ref<HTMLElement | null>(null)

onMounted(async () => {
  // Fetch real data from OpenCode API
  await store.fetchModels()
  await store.fetchTasks()

  // Animate hero elements
  gsap.from('.hero-title', {
    y: 50,
    opacity: 0,
    duration: 1,
    ease: 'power3.out',
  })

  gsap.from('.hero-subtitle', {
    y: 30,
    opacity: 0,
    duration: 1,
    delay: 0.3,
    ease: 'power3.out',
  })

  gsap.from('.hero-cta', {
    y: 20,
    opacity: 0,
    duration: 1,
    delay: 0.6,
    ease: 'power3.out',
  })

  // Animate stats
  gsap.from('.stat-card', {
    y: 40,
    opacity: 0,
    duration: 0.8,
    stagger: 0.1,
    ease: 'power3.out',
    scrollTrigger: {
      trigger: statsRef.value,
      start: 'top 80%',
    },
  })

  // Animate model cards
  gsap.from('.model-card', {
    y: 60,
    opacity: 0,
    duration: 0.8,
    stagger: 0.15,
    ease: 'power3.out',
    scrollTrigger: {
      trigger: modelsRef.value,
      start: 'top 80%',
    },
  })
})

const stats = [
  { label: t('stats.models'), value: '5', icon: 'brain', color: 'blue' },
  { label: t('stats.tasks'), value: '50+', icon: 'code', color: 'cyan' },
  { label: t('stats.languages'), value: '2', icon: 'language', color: 'violet' },
  { label: t('stats.runs'), value: '150+', icon: 'play', color: 'emerald' },
]

const features = [
  {
    title: t('features.controlledEnv.title'),
    description: t('features.controlledEnv.description'),
    icon: 'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z',
  },
  {
    title: t('features.fairComparison.title'),
    description: t('features.fairComparison.description'),
    icon: 'M12 3v17.25a.75.75 0 01-1.136.643L7.5 18.75l-3.364 1.643A.75.75 0 013 19.75V5.25c0-.414.336-.75.75-.75h16.5c.414 0 .75.336.75.75v11.25a.75.75 0 01-1.136.643L16.5 16.5l-3.364 1.643A.75.75 0 0112 17.25V3z',
  },
  {
    title: t('features.comprehensive.title'),
    description: t('features.comprehensive.description'),
    icon: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v4.125c0 .621-.504 1.125-1.125 1.125h-2.25A1.125 1.125 0 013 17.25V13.125zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v8.625c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM18.75 5.25c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v12c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V5.25z',
  },
]
</script>

<template>
  <div>
    <!-- Hero Section -->
    <section ref="heroRef" class="relative min-h-screen flex items-center justify-center overflow-hidden">
      <ParticleBackground />

      <div class="relative z-10 max-w-6xl mx-auto px-6 text-center">
        <div class="hero-title mb-6">
          <span class="inline-block px-4 py-1.5 rounded-full text-sm font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-6">
            {{ t('hero.badge') }}
          </span>
          <h1 class="text-5xl md:text-7xl font-bold tracking-tight mb-4">
            <span class="gradient-text">{{ t('hero.title') }}</span>
          </h1>
          <p class="text-xl md:text-2xl text-kimi-muted max-w-2xl mx-auto leading-relaxed">
            {{ t('hero.subtitle') }}
          </p>
        </div>

        <p class="hero-subtitle text-kimi-muted text-lg max-w-xl mx-auto mb-10 leading-relaxed">
          {{ t('hero.description') }}
        </p>

        <div class="hero-cta flex flex-col sm:flex-row gap-4 justify-center">
          <button
            class="btn-primary text-lg px-8 py-4"
            @click="router.push('/arena')"
          >
            <span class="flex items-center gap-2">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
              {{ t('hero.startArena') }}
            </span>
          </button>
          <button
            class="btn-secondary text-lg px-8 py-4"
            @click="router.push('/leaderboard')"
          >
            {{ t('hero.viewLeaderboard') }}
          </button>
        </div>
      </div>

      <!-- Scroll indicator -->
      <div class="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <svg class="w-6 h-6 text-kimi-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>
    </section>

    <!-- Stats Section -->
    <section ref="statsRef" class="py-24 relative">
      <div class="max-w-6xl mx-auto px-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <StatCard
            v-for="stat in stats"
            :key="stat.label"
            v-bind="stat"
            class="stat-card"
          />
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="py-24 relative">
      <div class="max-w-6xl mx-auto px-6">
        <div class="text-center mb-16">
          <h2 class="text-3xl md:text-4xl font-bold mb-4">
            {{ t('features.title') }} <span class="gradient-text">LLM Arena?</span>
          </h2>
          <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
            {{ t('features.subtitle') }}
          </p>
        </div>

        <div class="grid md:grid-cols-3 gap-8">
          <div
            v-for="feature in features"
            :key="feature.title"
            class="glass-card-hover p-8"
          >
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center mb-6">
              <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="feature.icon" />
              </svg>
            </div>
            <h3 class="text-xl font-semibold mb-3">{{ feature.title }}</h3>
            <p class="text-kimi-muted leading-relaxed">{{ feature.description }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Models Section -->
    <section ref="modelsRef" class="py-24 relative">
      <div class="max-w-6xl mx-auto px-6">
        <div class="text-center mb-16">
          <h2 class="text-3xl md:text-4xl font-bold mb-4">
            {{ t('models.title') }} <span class="gradient-text">Models</span>
          </h2>
          <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
            {{ t('models.subtitle') }}
          </p>
        </div>

        <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <ModelCard
            v-for="model in store.models"
            :key="model.id"
            :model="model"
            class="model-card"
          />
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-24 relative">
      <div class="max-w-4xl mx-auto px-6">
        <div class="gradient-border p-12 text-center">
          <h2 class="text-3xl md:text-4xl font-bold mb-4">
            {{ t('cta.title') }} <span class="gradient-text">Benchmark?</span>
          </h2>
          <p class="text-kimi-muted text-lg mb-8 max-w-xl mx-auto">
            {{ t('cta.subtitle') }}
          </p>
          <button
            class="btn-primary text-lg px-8 py-4"
            @click="router.push('/arena')"
          >
            <span class="flex items-center gap-2">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
              {{ t('cta.button') }}
            </span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>
