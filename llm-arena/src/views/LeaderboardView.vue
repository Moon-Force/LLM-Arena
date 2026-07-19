<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import gsap from 'gsap'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import type { LeaderboardType } from '@/types'

const store = useArenaStore()
const { t, locale } = useI18n()
const activeTab = ref<LeaderboardType>('overall')

const tabs = computed(() => [
  { key: 'overall' as LeaderboardType, label: t('leaderboard.tabs.overall'), icon: '🏆' },
  { key: 'accuracy' as LeaderboardType, label: t('leaderboard.tabs.accuracy'), icon: '🎯' },
  { key: 'value' as LeaderboardType, label: t('leaderboard.tabs.value'), icon: '💰' },
])

function setActiveTab(type: LeaderboardType) {
  activeTab.value = type
  store.setLeaderboardType(type)
}

function trackLabel(tr: { id: string; name?: { zh?: string; en?: string } | string }): string {
  const n = tr.name
  if (!n) return tr.id
  if (typeof n === 'string') return n
  return (locale.value === 'zh' ? n.zh : n.en) || n.zh || n.en || tr.id
}

function setTrack(trackId: string) {
  store.setLeaderboardTrack(trackId)
}

onMounted(async () => {
  await store.fetchTracks()
  await store.fetchRuns()
  gsap.from('.leaderboard-header', {
    y: 30,
    opacity: 0,
    duration: 0.8,
    ease: 'power3.out',
  })

  gsap.from('.leaderboard-row', {
    y: 20,
    opacity: 0,
    duration: 0.6,
    stagger: 0.08,
    ease: 'power3.out',
    delay: 0.3,
  })
})

function getRankStyle(index: number) {
  if (index === 0) return 'bg-[#e8c547]/20 text-[#e8c547] border-[#e8c547]/35'
  if (index === 1) return 'bg-white/10 text-[#d4cdc0] border-white/20'
  if (index === 2) return 'bg-[#ff5c33]/15 text-[#ff8a66] border-[#ff5c33]/30'
  return 'bg-white/[0.03] text-[#7a7368] border-white/10'
}

function getScoreColor(score: number) {
  if (score >= 90) return 'text-[#3dd6c6]'
  if (score >= 70) return 'text-[#ff8a66]'
  if (score >= 50) return 'text-[#e8c547]'
  return 'text-[#ff4d6d]'
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`
}

function formatNumber(value: number) {
  return value.toFixed(0)
}
</script>

<template>
  <div class="min-h-screen py-16 md:py-20 px-5 md:px-8">
    <div class="max-w-[1200px] mx-auto">
      <!-- Header -->
      <div class="leaderboard-header mb-12 max-w-2xl">
        <div class="eyebrow mb-3">Standings</div>
        <h1 class="display-title text-4xl md:text-6xl mb-4">
          <span class="gradient-text">{{ t('leaderboard.title') }}</span>
        </h1>
        <p class="text-[#9a9488] text-lg leading-relaxed">
          {{ t('leaderboard.subtitle') }}
        </p>
      </div>

      <!-- Track filter: scores only comparable within the same track -->
      <div class="flex flex-wrap gap-2 mb-6">
        <button
          type="button"
          class="px-3 py-1.5 rounded-md text-xs border font-mono font-medium transition-all"
          :class="store.selectedLeaderboardTrack === 'all'
            ? 'border-[#ff5c33]/50 bg-[#ff5c33]/15 text-[#ff8a66]'
            : 'border-white/10 text-[#7a7368] hover:text-[#f3efe6]'"
          @click="setTrack('all')"
        >
          {{ t('tracks.all') }}
        </button>
        <button
          v-for="tr in store.tracks.filter(x => x.enabled || (x.task_count || 0) > 0)"
          :key="tr.id"
          type="button"
          class="px-3 py-1.5 rounded-md text-xs border font-mono font-medium transition-all"
          :class="store.selectedLeaderboardTrack === tr.id
            ? 'border-[#ff5c33]/50 bg-[#ff5c33]/15 text-[#ff8a66]'
            : 'border-white/10 text-[#7a7368] hover:text-[#f3efe6]'"
          @click="setTrack(tr.id)"
        >
          {{ trackLabel(tr) }}
          <span v-if="tr.task_count != null" class="opacity-60 ml-1">{{ tr.task_count }}</span>
        </button>
      </div>
      <p class="text-[11px] text-[#7a7368] mb-8 max-w-xl">
        {{ t('leaderboard.byTrackHint') }}
      </p>

      <!-- Score-type Tabs -->
      <div class="flex mb-10">
        <div class="inline-flex bg-white/[0.03] rounded-xl p-1 border border-white/[0.08]">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="[
              'px-5 py-2.5 rounded-lg text-sm font-display font-semibold transition-all duration-300 flex items-center gap-2',
              activeTab === tab.key
                ? 'bg-gradient-to-r from-[#ff8a66] to-[#ff5c33] text-[#1a0c08] shadow-duel'
                : 'text-[#7a7368] hover:text-[#f3efe6]',
            ]"
            @click="setActiveTab(tab.key)"
          >
            <span>{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- Leaderboard Table -->
      <div class="glass-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-kimi-border/50">
                <th class="px-6 py-4 text-left text-xs font-medium text-kimi-muted uppercase tracking-wider w-16">{{ t('leaderboard.table.rank') }}</th>
                <th class="px-6 py-4 text-left text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.model') }}</th>
                <th class="px-6 py-4 text-left text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.provider') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.runs') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.passRate') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.hidden') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.stability') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.quality') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.safety') }}</th>
                <th class="px-6 py-4 text-center text-xs font-medium text-kimi-muted uppercase tracking-wider">{{ t('leaderboard.table.score') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(entry, index) in store.leaderboard"
                :key="entry.modelId"
                class="leaderboard-row border-b border-kimi-border/30 hover:bg-kimi-surface-hover/50 transition-colors duration-200"
              >
                <td class="px-6 py-4">
                  <span
                    class="inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold border"
                    :class="getRankStyle(index)"
                  >
                    {{ index + 1 }}
                  </span>
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-3">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                      :style="{ backgroundColor: entry.modelColor }"
                    >
                      {{ entry.modelName.charAt(0) }}
                    </div>
                    <span class="font-medium text-kimi-text">{{ entry.modelName }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 text-sm text-kimi-muted">{{ entry.modelProvider }}</td>
                <td class="px-6 py-4 text-center text-sm text-kimi-text">{{ entry.runs }}</td>
                <td class="px-6 py-4 text-center">
                  <div class="flex items-center justify-center gap-2">
                    <div class="w-24 h-2 bg-kimi-surface rounded-full overflow-hidden">
                      <div
                        class="h-full bg-blue-500 rounded-full transition-all duration-500"
                        :style="{ width: `${entry.passRate}%` }"
                      />
                    </div>
                    <span class="text-sm font-medium" :class="getScoreColor(entry.passRate)">{{ formatPercent(entry.passRate) }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 text-center">
                  <div class="flex items-center justify-center gap-2">
                    <div class="w-24 h-2 bg-kimi-surface rounded-full overflow-hidden">
                      <div
                        class="h-full bg-cyan-500 rounded-full transition-all duration-500"
                        :style="{ width: `${entry.hiddenPassRate}%` }"
                      />
                    </div>
                    <span class="text-sm font-medium" :class="getScoreColor(entry.hiddenPassRate)">{{ formatPercent(entry.hiddenPassRate) }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 text-center">
                  <span class="text-sm font-medium" :class="getScoreColor(entry.stability)">{{ formatPercent(entry.stability) }}</span>
                </td>
                <td class="px-6 py-4 text-center">
                  <span class="text-sm font-medium" :class="getScoreColor(entry.codeQuality)">{{ formatNumber(entry.codeQuality) }}</span>
                </td>
                <td class="px-6 py-4 text-center">
                  <span class="text-sm font-medium" :class="getScoreColor(entry.safetyScore)">{{ formatNumber(entry.safetyScore) }}</span>
                </td>
                <td class="px-6 py-4 text-center">
                  <span class="text-lg font-bold" :class="getScoreColor(entry.overallScore)">{{ entry.overallScore.toFixed(1) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
