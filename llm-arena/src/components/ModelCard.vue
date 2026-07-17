<script setup lang="ts">
import type { Model } from '@/types'

interface Props {
  model: Model
}

defineProps<Props>()
</script>

<template>
  <div class="glass-card-hover p-6 group cursor-pointer">
    <div class="flex items-start justify-between mb-4">
      <div class="flex items-center gap-3">
        <div
          class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
          :style="{ backgroundColor: model.color }"
        >
          {{ model.name.charAt(0) }}
        </div>
        <div>
          <h3 class="font-semibold text-kimi-text">{{ model.name }}</h3>
          <p class="text-xs text-kimi-muted">{{ model.provider }}</p>
        </div>
      </div>
      <span class="text-xs text-kimi-muted bg-kimi-surface px-2 py-1 rounded-lg">
        {{ model.version }}
      </span>
    </div>

    <p class="text-sm text-kimi-muted leading-relaxed mb-4">
      {{ model.description }}
    </p>

    <div class="flex items-center gap-2 text-xs text-kimi-muted">
      <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
      Active
    </div>
  </div>
</template>
