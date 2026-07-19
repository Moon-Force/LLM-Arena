<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { locale } = useI18n()

const currentLang = computed(() => locale.value)

const languages = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'zh', label: '中', name: '中文' },
]

function setLanguage(code: string) {
  locale.value = code
  localStorage.setItem('locale', code)
  document.documentElement.lang = code
}
</script>

<template>
  <div
    class="inline-flex items-center p-0.5 rounded-lg border border-white/[0.08] bg-white/[0.03]"
    role="group"
    aria-label="Language"
  >
    <button
      v-for="lang in languages"
      :key="lang.code"
      type="button"
      class="min-w-[2.25rem] px-2.5 py-1.5 rounded-md text-[11px] font-mono font-medium tracking-wide transition-all duration-300"
      :class="
        currentLang === lang.code
          ? 'bg-[#ff5c33] text-[#1a0c08] shadow-duel'
          : 'text-[#7a7368] hover:text-[#f3efe6]'
      "
      :title="lang.name"
      :aria-pressed="currentLang === lang.code"
      @click="setLanguage(lang.code)"
    >
      {{ lang.label }}
    </button>
  </div>
</template>
