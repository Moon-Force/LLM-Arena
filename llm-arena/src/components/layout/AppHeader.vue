<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const isScrolled = ref(false)
const mobileMenuOpen = ref(false)

const navItems = computed(() => [
  { name: t('nav.home'), path: '/' },
  { name: t('nav.leaderboard'), path: '/leaderboard' },
  { name: t('nav.arena'), path: '/arena' },
  { name: t('nav.outputs'), path: '/outputs' },
  { name: t('nav.comparison'), path: '/comparison' },
  { name: t('nav.models'), path: '/models' },
])

function handleScroll() {
  isScrolled.value = window.scrollY > 20
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <header
    :class="[
      'fixed top-0 left-0 right-0 z-50 transition-all duration-300',
      isScrolled
        ? 'bg-kimi-dark/80 backdrop-blur-xl border-b border-kimi-border/50'
        : 'bg-transparent',
    ]"
  >
    <div class="max-w-7xl mx-auto px-6">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <router-link
          to="/"
          class="flex items-center gap-3 group"
        >
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center group-hover:shadow-lg group-hover:shadow-blue-500/25 transition-all duration-300">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.25 9.75L16.5 12l-2.25 2.25m-4.5 0L7.5 12l2.25-2.25M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
            </svg>
          </div>
          <span class="font-bold text-lg text-kimi-text">LLM Arena</span>
        </router-link>

        <!-- Desktop Nav -->
        <nav class="hidden md:flex items-center gap-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
              route.path === item.path
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-kimi-muted hover:text-kimi-text hover:bg-kimi-surface',
            ]"
          >
            {{ item.name }}
          </router-link>
        </nav>

        <!-- Right side: Language Switcher -->
        <div class="hidden md:flex items-center gap-4">
          <LanguageSwitcher />
        </div>

        <!-- Mobile menu button -->
        <button
          class="md:hidden p-2 rounded-lg text-kimi-muted hover:text-kimi-text hover:bg-kimi-surface transition-colors"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              v-if="!mobileMenuOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
            />
            <path
              v-else
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile menu -->
    <transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="mobileMenuOpen"
        class="md:hidden bg-kimi-dark/95 backdrop-blur-xl border-b border-kimi-border/50"
      >
        <nav class="px-6 py-4 space-y-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'block px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
              route.path === item.path
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-kimi-muted hover:text-kimi-text hover:bg-kimi-surface',
            ]"
            @click="mobileMenuOpen = false"
          >
            {{ item.name }}
          </router-link>
        </nav>
        <div class="px-6 pb-4 pt-2 border-t border-kimi-border/30">
          <LanguageSwitcher />
        </div>
      </div>
    </transition>
  </header>
</template>
