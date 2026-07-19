<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '@/components/LanguageSwitcher.vue'
import CommandSearch from '@/components/CommandSearch.vue'

const route = useRoute()
const { t } = useI18n()
const isScrolled = ref(false)
const mobileMenuOpen = ref(false)

const navItems = computed(() => [
  { name: t('nav.home'), path: '/' },
  { name: t('nav.arena'), path: '/arena' },
  { name: t('nav.tasks'), path: '/tasks' },
  { name: t('nav.leaderboard'), path: '/leaderboard' },
  { name: t('nav.outputs'), path: '/outputs' },
  { name: t('nav.comparison'), path: '/comparison' },
  { name: t('nav.models'), path: '/models' },
])

function handleScroll() {
  isScrolled.value = window.scrollY > 12
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
    class="fixed top-0 left-0 right-0 z-50 transition-all duration-500"
    :class="
      isScrolled
        ? 'bg-[#0a0908]/78 backdrop-blur-2xl border-b border-white/[0.06] shadow-[0_12px_40px_-20px_rgba(0,0,0,0.8)]'
        : 'bg-transparent border-b border-transparent'
    "
  >
    <!-- top signal rail -->
    <div
      class="h-[2px] w-full origin-left transition-transform duration-700"
      :class="isScrolled ? 'scale-x-100' : 'scale-x-0'"
      style="background: linear-gradient(90deg, transparent, #ff5c33 20%, #e8c547 55%, #3dd6c6 80%, transparent)"
    />

    <div class="max-w-[1480px] mx-auto px-5 md:px-8">
      <div class="flex items-center justify-between h-[4.25rem]">
        <!-- Wordmark -->
        <router-link to="/" class="group flex items-center gap-3 min-w-0">
          <div
            class="relative w-10 h-10 shrink-0 rounded-[10px] flex items-center justify-center overflow-hidden
                   border border-white/10 bg-gradient-to-br from-[#2a1a14] to-[#12100e]
                   group-hover:border-[#ff5c33]/50 transition-all duration-400 group-hover:shadow-duel"
          >
            <span class="font-display font-extrabold text-[15px] tracking-tighter text-[#ff7a55]">LL</span>
            <span
              class="absolute -bottom-px left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-[#ff5c33] to-transparent
                     scale-x-0 group-hover:scale-x-100 transition-transform duration-500"
            />
          </div>
          <div class="leading-none min-w-0">
            <div class="font-display font-extrabold text-[1.05rem] tracking-tight text-[#f3efe6] truncate">
              LLM <span class="text-[#ff5c33]">Arena</span>
            </div>
            <div class="font-mono text-[9px] tracking-[0.22em] uppercase text-[#7a7368] mt-1 hidden sm:block">
              Colosseum Protocol
            </div>
          </div>
        </router-link>

        <!-- Desktop nav -->
        <nav class="hidden lg:flex items-center gap-0.5 p-1 rounded-xl bg-white/[0.02] border border-white/[0.05]">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="relative px-3.5 py-2 rounded-lg text-[13px] font-display font-semibold tracking-tight transition-all duration-300"
            :class="
              route.path === item.path
                ? 'text-[#1a0c08] bg-gradient-to-r from-[#ff8a66] to-[#ff5c33] shadow-duel'
                : 'text-[#9a9488] hover:text-[#f3efe6] hover:bg-white/[0.04]'
            "
          >
            {{ item.name }}
          </router-link>
        </nav>

        <div class="hidden md:flex items-center gap-3">
          <CommandSearch />
          <LanguageSwitcher />
          <router-link
            to="/arena"
            class="btn-primary !py-2 !px-4 !text-[13px] hidden xl:inline-flex"
          >
            {{ t('nav.arena') }}
          </router-link>
        </div>

        <button
          type="button"
          class="lg:hidden p-2.5 rounded-lg text-[#9a9488] hover:text-[#f3efe6] hover:bg-white/[0.04] border border-transparent hover:border-white/10 transition-all"
          :aria-expanded="mobileMenuOpen"
          aria-label="Menu"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              v-if="!mobileMenuOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.75"
              d="M4 7h16M4 12h16M4 17h10"
            />
            <path
              v-else
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.75"
              d="M6 6l12 12M18 6L6 18"
            />
          </svg>
        </button>
      </div>
    </div>

    <transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="mobileMenuOpen"
        class="lg:hidden border-t border-white/[0.06] bg-[#0a0908]/95 backdrop-blur-2xl"
      >
        <nav class="px-5 py-4 space-y-1">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="block px-4 py-3 rounded-lg text-sm font-display font-semibold transition-all"
            :class="
              route.path === item.path
                ? 'text-[#ff7a55] bg-[#ff5c33]/10 border border-[#ff5c33]/20'
                : 'text-[#9a9488] hover:text-[#f3efe6] hover:bg-white/[0.03]'
            "
            @click="mobileMenuOpen = false"
          >
            {{ item.name }}
          </router-link>
        </nav>
        <div class="px-5 pb-5 pt-2 border-t border-white/[0.05] flex items-center justify-between">
          <LanguageSwitcher />
          <router-link to="/arena" class="btn-primary !py-2 !px-4 !text-sm" @click="mobileMenuOpen = false">
            {{ t('nav.arena') }}
          </router-link>
        </div>
      </div>
    </transition>
  </header>
</template>
