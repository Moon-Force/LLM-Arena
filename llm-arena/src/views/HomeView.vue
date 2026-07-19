<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ModelCard from '@/components/ModelCard.vue'
import StatCard from '@/components/StatCard.vue'
import { useArenaStore } from '@/stores/arena'

const router = useRouter()
const store = useArenaStore()
const { t } = useI18n()

onMounted(async () => {
  await Promise.all([store.fetchModels(), store.fetchTasks()])
})

const stats = computed(() => [
  {
    label: t('stats.models'),
    value: String(store.models.length || '—'),
    icon: 'brain',
    color: 'signal',
  },
  {
    label: t('stats.tasks'),
    value: String(store.tasks.length || '—'),
    icon: 'code',
    color: 'verify',
  },
  {
    label: t('stats.languages'),
    value: '2',
    icon: 'language',
    color: 'rank',
  },
  {
    label: t('stats.runs'),
    value: String(store.runs.length || '0'),
    icon: 'play',
    color: 'signal',
  },
])

const features = computed(() => [
  {
    title: t('features.controlledEnv.title'),
    description: t('features.controlledEnv.description'),
    index: '01',
  },
  {
    title: t('features.fairComparison.title'),
    description: t('features.fairComparison.description'),
    index: '02',
  },
  {
    title: t('features.comprehensive.title'),
    description: t('features.comprehensive.description'),
    index: '03',
  },
])

const ticker = [
  'SINGLE VARIABLE',
  'OPENCODE ENGINE',
  'DOCKER ISOLATION',
  'PYTEST JUDGE',
  'TRACK PARTITION',
  'FROZEN TOOLS',
]
</script>

<template>
  <div class="pb-24">
    <!-- HERO: asymmetric arena entrance -->
    <section class="relative min-h-[92vh] flex items-center overflow-hidden">
      <!-- diagonal slab -->
      <div
        class="pointer-events-none absolute -right-[12%] top-[8%] w-[58%] h-[72%] rotate-[-8deg] rounded-[28px]
               border border-white/[0.05] bg-gradient-to-br from-white/[0.035] to-transparent
               shadow-stage float-slow opacity-80"
      />
      <div
        class="pointer-events-none absolute right-[8%] top-[22%] w-40 h-40 rounded-full
               bg-[#ff5c33]/15 blur-[80px] pulse-signal"
      />

      <div class="relative z-10 w-full max-w-[1480px] mx-auto px-5 md:px-8 pt-10 pb-20">
        <div class="grid lg:grid-cols-12 gap-10 lg:gap-6 items-end">
          <div class="lg:col-span-7">
            <div class="reveal">
              <span class="eyebrow inline-flex items-center gap-2 mb-7">
                <span class="w-1.5 h-1.5 rounded-full bg-[#ff5c33] animate-pulse" />
                {{ t('hero.badge') }}
              </span>
            </div>

            <h1 class="display-title reveal stagger-1 text-[clamp(2.8rem,7.5vw,5.75rem)] text-balance">
              <span class="block text-[#f3efe6]">{{ t('hero.title') }}</span>
              <span class="block mt-2 gradient-text">{{ t('hero.subtitle') }}</span>
            </h1>

            <p
              class="reveal stagger-2 mt-7 max-w-xl text-lg md:text-xl text-[#9a9488] leading-relaxed text-balance"
            >
              {{ t('hero.description') }}
            </p>

            <div class="reveal stagger-3 mt-10 flex flex-col sm:flex-row gap-3 sm:items-center">
              <button type="button" class="btn-primary text-base px-8 py-4" @click="router.push('/arena')">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"
                  />
                </svg>
                {{ t('hero.startArena') }}
              </button>
              <button type="button" class="btn-secondary text-base px-8 py-4" @click="router.push('/leaderboard')">
                {{ t('hero.viewLeaderboard') }}
              </button>
            </div>
          </div>

          <!-- Protocol card -->
          <div class="lg:col-span-5 reveal stagger-4">
            <div class="glass-card p-6 md:p-8 relative lg:-mb-6 lg:translate-y-4">
              <div class="flex items-start justify-between gap-4 mb-6">
                <div>
                  <div class="font-mono text-[10px] tracking-[0.2em] text-[#7a7368] uppercase">Protocol</div>
                  <div class="font-display font-bold text-2xl mt-1 tracking-tight">Single Variable</div>
                </div>
                <div
                  class="font-mono text-[10px] px-2.5 py-1 rounded-full border border-[#3dd6c6]/30 text-[#3dd6c6] bg-[#3dd6c6]/10"
                >
                  LIVE
                </div>
              </div>

              <ul class="space-y-3 font-mono text-[12px] text-[#b8b0a2]">
                <li class="flex justify-between border-b border-white/[0.05] pb-2">
                  <span class="text-[#7a7368]">engine</span>
                  <span class="text-[#f3efe6]">opencode-ai</span>
                </li>
                <li class="flex justify-between border-b border-white/[0.05] pb-2">
                  <span class="text-[#7a7368]">judge</span>
                  <span class="text-[#f3efe6]">pytest pass@all</span>
                </li>
                <li class="flex justify-between border-b border-white/[0.05] pb-2">
                  <span class="text-[#7a7368]">isolation</span>
                  <span class="text-[#f3efe6]">workspace / docker</span>
                </li>
                <li class="flex justify-between">
                  <span class="text-[#7a7368]">free variable</span>
                  <span class="text-[#ff7a55]">model only</span>
                </li>
              </ul>

              <div class="mt-7 grid grid-cols-2 gap-3">
                <div class="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
                  <div class="font-display text-2xl font-bold text-[#ff5c33]">
                    {{ store.models.length || '—' }}
                  </div>
                  <div class="text-xs text-[#7a7368] mt-0.5">{{ t('stats.models') }}</div>
                </div>
                <div class="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3">
                  <div class="font-display text-2xl font-bold text-[#3dd6c6]">
                    {{ store.tasks.length || '—' }}
                  </div>
                  <div class="text-xs text-[#7a7368] mt-0.5">{{ t('stats.tasks') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- bottom marquee -->
      <div
        class="absolute bottom-0 left-0 right-0 border-t border-white/[0.05] bg-[#0a0908]/60 backdrop-blur-md overflow-hidden"
      >
        <div class="flex whitespace-nowrap animate-marquee py-3 font-mono text-[11px] tracking-[0.25em] text-[#7a7368]">
          <span v-for="n in 2" :key="n" class="flex">
            <span v-for="(item, i) in ticker" :key="`${n}-${i}`" class="mx-8">
              <span class="text-[#ff5c33]">✦</span> {{ item }}
            </span>
          </span>
        </div>
      </div>
    </section>

    <!-- Stats -->
    <section class="py-20 md:py-28">
      <div class="max-w-[1480px] mx-auto px-5 md:px-8">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5">
          <StatCard
            v-for="(stat, i) in stats"
            :key="stat.label"
            v-bind="stat"
            class="reveal"
            :class="`stagger-${i + 1}`"
          />
        </div>
      </div>
    </section>

    <!-- Features: offset editorial grid -->
    <section class="py-10 md:py-16">
      <div class="max-w-[1480px] mx-auto px-5 md:px-8">
        <div class="grid lg:grid-cols-12 gap-8 mb-12 items-end">
          <div class="lg:col-span-5">
            <div class="eyebrow mb-3">Why Arena</div>
            <h2 class="display-title text-4xl md:text-5xl">
              {{ t('features.title') }}
              <span class="gradient-text">LLM Arena</span>
            </h2>
          </div>
          <p class="lg:col-span-6 lg:col-start-7 text-[#9a9488] text-lg leading-relaxed max-w-xl">
            {{ t('features.subtitle') }}
          </p>
        </div>

        <div class="grid md:grid-cols-3 gap-5">
          <article
            v-for="(feature, i) in features"
            :key="feature.title"
            class="glass-card-hover p-7 md:p-8 group"
            :class="i === 1 ? 'md:translate-y-6' : i === 2 ? 'md:translate-y-3' : ''"
          >
            <div class="font-mono text-[11px] tracking-[0.2em] text-[#ff5c33]/80 mb-8">
              {{ feature.index }}
            </div>
            <h3 class="font-display font-bold text-xl md:text-2xl tracking-tight mb-3 group-hover:text-[#ff8a66] transition-colors">
              {{ feature.title }}
            </h3>
            <p class="text-[#9a9488] leading-relaxed">
              {{ feature.description }}
            </p>
          </article>
        </div>
      </div>
    </section>

    <!-- Models -->
    <section class="py-20 md:py-28">
      <div class="max-w-[1480px] mx-auto px-5 md:px-8">
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-12">
          <div>
            <div class="eyebrow mb-3">Roster</div>
            <h2 class="display-title text-4xl md:text-5xl">
              {{ t('models.title') }}
              <span class="gradient-text">Models</span>
            </h2>
          </div>
          <p class="text-[#9a9488] max-w-md">
            {{ t('models.subtitle') }}
          </p>
        </div>

        <div v-if="store.models.length" class="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          <ModelCard
            v-for="(model, i) in store.models"
            :key="model.id"
            :model="model"
            class="reveal"
            :class="`stagger-${Math.min(i + 1, 6)}`"
          />
        </div>
        <div
          v-else
          class="glass-card p-12 text-center text-[#7a7368]"
        >
          Connect the API and configure models to populate the roster.
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="pb-8">
      <div class="max-w-[980px] mx-auto px-5 md:px-8">
        <div class="gradient-border p-10 md:p-14 text-center relative overflow-hidden">
          <div
            class="pointer-events-none absolute -top-20 left-1/2 -translate-x-1/2 w-72 h-72 rounded-full bg-[#ff5c33]/10 blur-[70px]"
          />
          <div class="relative">
            <div class="eyebrow mb-4 justify-center inline-flex">Enter the ring</div>
            <h2 class="display-title text-3xl md:text-5xl mb-4">
              {{ t('cta.title') }}
              <span class="gradient-text">Benchmark</span>
            </h2>
            <p class="text-[#9a9488] text-lg mb-9 max-w-lg mx-auto">
              {{ t('cta.subtitle') }}
            </p>
            <button type="button" class="btn-primary text-base px-9 py-4" @click="router.push('/arena')">
              {{ t('cta.button') }}
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
