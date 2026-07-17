<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import gsap from 'gsap'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import type { LeaderboardType } from '@/types'

const store = useArenaStore()
const { t } = useI18n()
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

onMounted(() => {
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
  if (index === 0) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
  if (index === 1) return 'bg-gray-400/20 text-gray-300 border-gray-400/30'
  if (index === 2) return 'bg-amber-600/20 text-amber-400 border-amber-600/30'
  return 'bg-kimi-surface text-kimi-muted border-kimi-border'
}

function getScoreColor(score: number) {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 70) return 'text-blue-400'
  if (score >= 50) return 'text-amber-400'
  return 'text-rose-400'
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`
}

function formatNumber(value: number) {
  return value.toFixed(0)
}
</script>

<template>
  <div class="min-h-screen py-24 px-6">
    <div class="max-w-7xl mx-auto">
      <!-- Header -->
      <div class="leaderboard-header text-center mb-12">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          <span class="gradient-text">{{ t('leaderboard.title') }}</span>
        </h1>
        <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
          {{ t('leaderboard.subtitle') }}
        </p>
      </div>

      <!-- Tabs -->
      <div class="flex justify-center mb-10">
        <div class="inline-flex bg-kimi-surface rounded-xl p-1 border border-kimi-border">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            :class="[
              'px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2',
              activeTab === tab.key
                ? 'bg-blue-500/10 text-blue-400'
                : 'text-kimi-muted hover:text-kimi-text',
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
