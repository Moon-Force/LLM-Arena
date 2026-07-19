<script setup lang="ts">
import type { Model } from '@/types'

interface Props {
  model: Model
}

defineProps<Props>()
</script>

<template>
  <div class="glass-card-hover p-6 group cursor-default">
    <div class="flex items-start justify-between gap-3 mb-5">
      <div class="flex items-center gap-3 min-w-0">
        <div
          class="w-11 h-11 rounded-[10px] flex items-center justify-center text-white font-display font-extrabold text-sm shrink-0
                 ring-1 ring-white/10 shadow-lg transition-transform duration-400 group-hover:scale-105 group-hover:rotate-[-3deg]"
          :style="{ backgroundColor: model.color || '#ff5c33' }"
        >
          {{ model.name?.charAt(0) || '?' }}
        </div>
        <div class="min-w-0">
          <h3 class="font-display font-bold text-[#f3efe6] tracking-tight truncate">
            {{ model.name }}
          </h3>
          <p class="font-mono text-[11px] text-[#7a7368] mt-0.5 truncate">
            {{ model.provider }}
          </p>
        </div>
      </div>
      <span
        class="shrink-0 font-mono text-[10px] tracking-wide text-[#b8b0a2] bg-white/[0.04] border border-white/[0.06] px-2 py-1 rounded-md"
      >
        {{ model.version }}
      </span>
    </div>

    <p class="text-sm text-[#9a9488] leading-relaxed mb-5 line-clamp-3">
      {{ model.description || 'Configured for fair arena matches under frozen constraints.' }}
    </p>

    <div class="flex items-center justify-between pt-3 border-t border-white/[0.05]">
      <div class="flex items-center gap-2 text-[11px] font-mono text-[#7a7368]">
        <span
          class="w-1.5 h-1.5 rounded-full"
          :class="model.enabled === false ? 'bg-[#7a7368]' : 'bg-[#3dd6c6] shadow-[0_0_8px_#3dd6c6]'"
        />
        {{ model.enabled === false ? 'Disabled' : 'Ready' }}
      </div>
      <span class="text-[11px] font-mono text-[#ff5c33]/70 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        duel-ready →
      </span>
    </div>
  </div>
</template>
