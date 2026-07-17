<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'

const store = useArenaStore()
const { t } = useI18n()
const selectedModels = ref<string[]>([])
const compareMetric = ref<'passRate' | 'hiddenPassRate' | 'codeQuality' | 'stability'>('passRate')

const metricLabels = computed(() => ({
  passRate: t('leaderboard.table.passRate'),
  hiddenPassRate: t('leaderboard.table.hidden'),
  codeQuality: t('leaderboard.table.quality'),
  stability: t('leaderboard.table.stability'),
}))

const selectedModelData = computed(() => {
  return store.models.filter(m => selectedModels.value.includes(m.id))
})

function toggleModel(modelId: string) {
  if (selectedModels.value.includes(modelId)) {
    selectedModels.value = selectedModels.value.filter(id => id !== modelId)
  } else if (selectedModels.value.length < 3) {
    selectedModels.value.push(modelId)
  }
}

function getBarWidth(value: number) {
  return `${Math.min(value, 100)}%`
}
</script>

<template>
  <div class="min-h-screen py-24 px-6">
    <div class="max-w-7xl mx-auto">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          <span class="gradient-text">{{ t('comparison.title') }}</span>
        </h1>
        <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
          {{ t('comparison.subtitle') }}
        </p>
      </div>

      <!-- Model Selection -->
      <div class="glass-card p-6 mb-8">
        <h2 class="text-lg font-semibold mb-4">{{ t('comparison.selectModels') }}</h2>
        <div class="flex flex-wrap gap-3">
          <button
            v-for="model in store.models"
            :key="model.id"
            :class="[
              'flex items-center gap-2 px-4 py-2 rounded-xl border transition-all duration-200',
              selectedModels.includes(model.id)
                ? 'border-blue-500/50 bg-blue-500/10'
                : 'border-kimi-border hover:border-kimi-border-hover bg-kimi-surface',
            ]"
            @click="toggleModel(model.id)"
          >
            <div
              class="w-6 h-6 rounded-md flex items-center justify-center text-white text-xs font-bold"
              :style="{ backgroundColor: model.color }"
            >
              {{ model.name.charAt(0) }}
            </div>
            <span class="text-sm font-medium">{{ model.name }}</span>
          </button>
        </div>
      </div>

      <!-- Comparison Charts -->
      <div v-if="selectedModels.length > 0" class="space-y-6">
        <!-- Metric Selector -->
        <div class="flex flex-wrap gap-2">
          <button
            v-for="(label, key) in metricLabels"
            :key="key"
            :class="[
              'px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200',
              compareMetric === key
                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                : 'bg-kimi-surface text-kimi-muted border border-kimi-border hover:border-kimi-border-hover',
            ]"
            @click="compareMetric = key"
          >
            {{ label }}
          </button>
        </div>

        <!-- Comparison Bars -->
        <div class="glass-card p-6">
          <h3 class="text-lg font-semibold mb-6">{{ metricLabels[compareMetric] }} {{ t('comparison.title') }}</h3>
          <div class="space-y-4">
            <div
              v-for="model in selectedModelData"
              :key="model.id"
              class="flex items-center gap-4"
            >
              <div class="w-32 flex-shrink-0 flex items-center gap-2">
                <div
                  class="w-6 h-6 rounded-md flex items-center justify-center text-white text-xs font-bold"
                  :style="{ backgroundColor: model.color }"
                >
                  {{ model.name.charAt(0) }}
                </div>
                <span class="text-sm font-medium text-kimi-text">{{ model.name }}</span>
              </div>
              <div class="flex-1">
                <div class="h-8 bg-kimi-surface rounded-lg overflow-hidden">
                  <div
                    class="h-full rounded-lg transition-all duration-500 flex items-center justify-end pr-3"
                    :style="{
                      width: getBarWidth(Math.random() * 30 + 70),
                      backgroundColor: model.color + '40',
                      borderRight: `3px solid ${model.color}`,
                    }"
                  >
                    <span class="text-xs font-medium text-kimi-text">{{ (Math.random() * 30 + 70).toFixed(1) }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Radar Chart Placeholder -->
        <div class="glass-card p-6">
          <h3 class="text-lg font-semibold mb-6">{{ t('comparison.multiDimensional') }}</h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div
              v-for="metric in ['Pass Rate', 'Hidden Pass', 'Code Quality', 'Stability', 'Safety', 'Speed', 'Cost Efficiency', 'Consistency']"
              :key="metric"
              class="p-4 rounded-xl bg-kimi-surface/50 border border-kimi-border/30"
            >
              <div class="text-xs text-kimi-muted mb-2">{{ metric }}</div>
              <div class="space-y-2">
                <div
                  v-for="model in selectedModelData"
                  :key="model.id"
                  class="flex items-center gap-2"
                >
                  <div
                    class="w-2 h-2 rounded-full flex-shrink-0"
                    :style="{ backgroundColor: model.color }"
                  />
                  <div class="flex-1">
                    <div class="h-1.5 bg-kimi-surface rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all duration-500"
                        :style="{
                          width: `${Math.random() * 30 + 60}%`,
                          backgroundColor: model.color,
                        }"
                      />
                    </div>
                  </div>
                  <span class="text-xs text-kimi-muted w-8 text-right">{{ (Math.random() * 30 + 60).toFixed(0) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-12">
        <div class="w-16 h-16 rounded-2xl bg-kimi-surface flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-kimi-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
        </div>
        <p class="text-kimi-muted">{{ t('comparison.selectModels') }}</p>
      </div>
    </div>
  </div>
</template>
