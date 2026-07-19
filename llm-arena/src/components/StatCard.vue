<script setup lang="ts">
interface Props {
  label: string
  value: string
  icon: string
  color: string
}

defineProps<Props>()

const colorMap: Record<string, { rail: string; text: string; soft: string }> = {
  blue: { rail: 'from-[#ff5c33]', text: 'text-[#ff7a55]', soft: 'bg-[#ff5c33]/10' },
  cyan: { rail: 'from-[#3dd6c6]', text: 'text-[#3dd6c6]', soft: 'bg-[#3dd6c6]/10' },
  violet: { rail: 'from-[#c4a1ff]', text: 'text-[#c4a1ff]', soft: 'bg-[#c4a1ff]/10' },
  emerald: { rail: 'from-[#3dd6c6]', text: 'text-[#3dd6c6]', soft: 'bg-[#3dd6c6]/10' },
  signal: { rail: 'from-[#ff5c33]', text: 'text-[#ff7a55]', soft: 'bg-[#ff5c33]/10' },
  verify: { rail: 'from-[#3dd6c6]', text: 'text-[#3dd6c6]', soft: 'bg-[#3dd6c6]/10' },
  rank: { rail: 'from-[#e8c547]', text: 'text-[#e8c547]', soft: 'bg-[#e8c547]/10' },
}

const iconMap: Record<string, string> = {
  brain:
    'M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18',
  code: 'M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5',
  language:
    'M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621l6.237-2.34m0 0A7.5 7.5 0 1018.571 8.214M3 5.621l6.237 2.34M3 5.621v12.758l6.237-2.34',
  play: 'M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z',
}
</script>

<template>
  <div class="glass-card p-5 md:p-6 group">
    <div class="flex items-start justify-between mb-5">
      <div
        class="w-10 h-10 rounded-lg flex items-center justify-center transition-transform duration-400 group-hover:scale-110"
        :class="(colorMap[color] || colorMap.signal).soft"
      >
        <svg
          class="w-5 h-5"
          :class="(colorMap[color] || colorMap.signal).text"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" :d="iconMap[icon]" />
        </svg>
      </div>
      <div
        class="h-8 w-px bg-gradient-to-b to-transparent opacity-70"
        :class="(colorMap[color] || colorMap.signal).rail"
      />
    </div>
    <div
      class="font-display text-3xl md:text-4xl font-extrabold tracking-tight mb-1 tabular-nums"
      :class="(colorMap[color] || colorMap.signal).text"
    >
      {{ value }}
    </div>
    <div class="text-sm text-[#7a7368] font-mono tracking-wide">{{ label }}</div>
  </div>
</template>
