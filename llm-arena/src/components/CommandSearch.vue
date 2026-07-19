<script setup lang="ts">
/**
 * In-app project search (Ctrl/Cmd+K): pages, tracks, tasks, models.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'

const open = ref(false)
const query = ref('')
const active = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const router = useRouter()
const store = useArenaStore()
const { t, locale } = useI18n()

type Hit = {
  id: string
  kind: 'page' | 'task' | 'model' | 'track'
  title: string
  subtitle: string
  path?: string
  action?: () => void
}

const pages = computed<Hit[]>(() => [
  { id: 'p-home', kind: 'page', title: t('nav.home'), subtitle: '/', path: '/' },
  { id: 'p-arena', kind: 'page', title: t('nav.arena'), subtitle: '/arena', path: '/arena' },
  { id: 'p-tasks', kind: 'page', title: t('nav.tasks'), subtitle: '/tasks', path: '/tasks' },
  { id: 'p-lb', kind: 'page', title: t('nav.leaderboard'), subtitle: '/leaderboard', path: '/leaderboard' },
  { id: 'p-out', kind: 'page', title: t('nav.outputs'), subtitle: '/outputs', path: '/outputs' },
  { id: 'p-cmp', kind: 'page', title: t('nav.comparison'), subtitle: '/comparison', path: '/comparison' },
  { id: 'p-models', kind: 'page', title: t('nav.models'), subtitle: '/models', path: '/models' },
])

const hits = computed(() => {
  const q = query.value.trim().toLowerCase()
  const all: Hit[] = [
    ...pages.value,
    ...store.tracks.map(tr => {
      const name =
        typeof tr.name === 'string'
          ? tr.name
          : (locale.value === 'zh' ? tr.name?.zh : tr.name?.en) || tr.id
      return {
        id: `tr-${tr.id}`,
        kind: 'track' as const,
        title: name,
        subtitle: `track · ${tr.id} · ${tr.task_count ?? 0} tasks`,
        action: () => {
          store.setSelectedTrack(tr.id)
          void store.fetchTasks(tr.id)
          router.push('/arena')
        },
      }
    }),
    ...store.tasks.map(task => ({
      id: `task-${task.id}`,
      kind: 'task' as const,
      title: task.name,
      subtitle: `${task.id} · ${task.track || '—'} · ${task.language} · ${task.difficulty}`,
      action: () => {
        if (task.track) {
          store.setSelectedTrack(String(task.track))
          void store.fetchTasks(String(task.track))
        }
        router.push('/arena')
      },
    })),
    ...store.models.map(m => ({
      id: `model-${m.id}`,
      kind: 'model' as const,
      title: m.name,
      subtitle: `${m.provider} · ${m.version}`,
      path: '/models',
    })),
  ]

  if (!q) return all.slice(0, 12)

  const scored = all
    .map(h => {
      const hay = `${h.title} ${h.subtitle} ${h.kind}`.toLowerCase()
      let score = 0
      if (h.title.toLowerCase().startsWith(q)) score += 40
      if (h.title.toLowerCase().includes(q)) score += 20
      if (hay.includes(q)) score += 10
      // multi-token AND
      const parts = q.split(/\s+/).filter(Boolean)
      if (parts.every(p => hay.includes(p))) score += 5 * parts.length
      return { h, score }
    })
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 20)
    .map(x => x.h)

  return scored
})

watch(hits, () => {
  active.value = 0
})

function openSearch() {
  open.value = true
  query.value = ''
  active.value = 0
  void nextTick(() => inputRef.value?.focus())
  // warm data
  void store.fetchTracks()
  void store.fetchTasks(store.selectedTrack)
  void store.fetchModels()
}

function closeSearch() {
  open.value = false
  query.value = ''
}

function runHit(hit: Hit) {
  closeSearch()
  if (hit.action) {
    hit.action()
    return
  }
  if (hit.path) router.push(hit.path)
}

function onKey(e: KeyboardEvent) {
  const mod = e.ctrlKey || e.metaKey
  if (mod && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (open.value) closeSearch()
    else openSearch()
    return
  }
  if (!open.value) return
  if (e.key === 'Escape') {
    e.preventDefault()
    closeSearch()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    active.value = Math.min(active.value + 1, Math.max(0, hits.value.length - 1))
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    active.value = Math.max(active.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const hit = hits.value[active.value]
    if (hit) runHit(hit)
  }
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

defineExpose({ openSearch })
</script>

<template>
  <!-- trigger -->
  <button
    type="button"
    class="hidden sm:inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03]
           text-[11px] font-mono text-[#7a7368] hover:text-[#f3efe6] hover:border-[#ff5c33]/35 transition-all"
    :title="t('search.hint')"
    @click="openSearch"
  >
    <svg class="w-3.5 h-3.5 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
    </svg>
    <span>{{ t('search.placeholderShort') }}</span>
    <kbd class="px-1.5 py-0.5 rounded border border-white/10 text-[10px] text-[#9a9488]">⌘K</kbd>
  </button>

  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] px-4"
      role="dialog"
      aria-modal="true"
      :aria-label="t('search.title')"
    >
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="closeSearch" />
      <div
        class="relative w-full max-w-xl rounded-2xl border border-white/10 bg-[#12100e] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.85)] overflow-hidden"
      >
        <div class="flex items-center gap-2 px-4 border-b border-white/[0.06]">
          <svg class="w-4 h-4 text-[#ff5c33] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z" />
          </svg>
          <input
            ref="inputRef"
            v-model="query"
            type="search"
            class="w-full bg-transparent py-3.5 text-sm text-[#f3efe6] placeholder:text-[#7a7368] outline-none font-body"
            :placeholder="t('search.placeholder')"
            autocomplete="off"
            spellcheck="false"
          >
          <button type="button" class="text-[11px] font-mono text-[#7a7368] hover:text-[#f3efe6]" @click="closeSearch">
            ESC
          </button>
        </div>

        <ul class="max-h-[50vh] overflow-y-auto py-2" role="listbox">
          <li v-if="!hits.length" class="px-4 py-6 text-center text-sm text-[#7a7368]">
            {{ t('search.empty') }}
          </li>
          <li
            v-for="(hit, i) in hits"
            :key="hit.id"
            role="option"
            :aria-selected="i === active"
            class="px-3 py-2 mx-2 rounded-lg cursor-pointer flex items-start gap-3 transition-colors"
            :class="i === active ? 'bg-[#ff5c33]/12 border border-[#ff5c33]/25' : 'border border-transparent hover:bg-white/[0.03]'"
            @mouseenter="active = i"
            @click="runHit(hit)"
          >
            <span
              class="mt-0.5 text-[10px] font-mono uppercase tracking-wider shrink-0 w-12"
              :class="{
                'text-[#ff8a66]': hit.kind === 'page',
                'text-[#3dd6c6]': hit.kind === 'task',
                'text-[#e8c547]': hit.kind === 'model',
                'text-[#c4a1ff]': hit.kind === 'track',
              }"
            >
              {{ hit.kind }}
            </span>
            <div class="min-w-0 flex-1">
              <div class="text-sm font-display font-semibold text-[#f3efe6] truncate">{{ hit.title }}</div>
              <div class="text-[11px] font-mono text-[#7a7368] truncate">{{ hit.subtitle }}</div>
            </div>
          </li>
        </ul>

        <div class="px-4 py-2 border-t border-white/[0.06] text-[10px] font-mono text-[#5c564c] flex gap-3">
          <span>↑↓ {{ t('search.navigate') }}</span>
          <span>↵ {{ t('search.open') }}</span>
          <span>esc {{ t('search.close') }}</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>
