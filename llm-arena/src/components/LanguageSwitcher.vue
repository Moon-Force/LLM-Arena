<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { locale } = useI18n()

const currentLang = computed(() => locale.value)

const languages = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'zh', label: '中', name: '中文' },
]

function toggleLanguage() {
  const newLocale = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = newLocale
  localStorage.setItem('locale', newLocale)
  document.documentElement.lang = newLocale
}

function setLanguage(code: string) {
  locale.value = code
  localStorage.setItem('locale', code)
  document.documentElement.lang = code
}
</script>

<template>
  <div class="flex items-center gap-1">
    <button
      v-for="lang in languages"
      :key="lang.code"
      :class="[
        'px-2 py-1 rounded-md text-xs font-medium transition-all duration-200',
        currentLang === lang.code
          ? 'bg-blue-500/20 text-blue-400'
          : 'text-kimi-muted hover:text-kimi-text hover:bg-kimi-surface',
      ]"
      @click="setLanguage(lang.code)"
      :title="lang.name"
    >
      {{ lang.label }}
    </button>
  </div>
</template>
