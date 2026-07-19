<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import { api } from '@/utils/api'
import type { OpencodeToolInfo, OpencodeToolsPayload } from '@/utils/api'
import type { ArenaRun } from '@/types'
import OpenCodeTerminal from '@/components/OpenCodeTerminal.vue'

const store = useArenaStore()
const { t } = useI18n()

const selectedModels = ref<string[]>([])
const selectedTask = ref<string | null>(null)
const parallel = ref(true)
const wsConnections = ref<Map<string, WebSocket>>(new Map())
const constraintsNote = ref('')
const constraintsFp = ref('')
const lastArenaId = ref<string | null>(null)
const opencodeTools = ref<OpencodeToolsPayload | null>(null)

const toolsByCategory = computed(() => {
  const list = opencodeTools.value?.tools || []
  const map = new Map<string, OpencodeToolInfo[]>()
  for (const tool of list) {
    const cat = tool.category || 'other'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(tool)
  }
  return [...map.entries()]
})

const matchRuns = ref<ArenaRun[]>([])
/** Default to OpenCode dialogue — what users asked for */
const panelTab = ref<Record<string, 'terminal' | 'page'>>({})
/** After a duel starts, collapse config so the match board owns the viewport */
const configCollapsed = ref(false)
const toolsCollapsed = ref(false)

const canStart = computed(
  () => selectedModels.value.length >= 2 && !!selectedTask.value && !store.isRunning,
)
const enabledModels = computed(() => store.models.filter(m => m.enabled !== false))
const showMatchBoard = computed(() => matchRuns.value.length > 0)
/** Compact chrome once a run is live or results are on screen */
const duelActive = computed(() => store.isRunning || showMatchBoard.value)

const selectedTrackMeta = computed(() =>
  store.tracks.find(tr => tr.id === store.selectedTrack) || null,
)
const selectedTaskMeta = computed(() =>
  store.tasks.find(t => t.id === selectedTask.value) || null,
)
const selectedModelNames = computed(() =>
  selectedModels.value
    .map(id => store.getModelById(id)?.name || id)
    .filter(Boolean),
)

function expandConfig() {
  configCollapsed.value = false
}

function collapseConfig() {
  configCollapsed.value = true
}

function trackLabel(track: { id: string; name?: { zh?: string; en?: string } | string }): string {
  const n = track.name
  if (!n) return track.id
  if (typeof n === 'string') return n
  return n.zh || n.en || track.id
}

async function selectTrack(trackId: string) {
  if (store.selectedTrack === trackId) return
  store.setSelectedTrack(trackId)
  selectedTask.value = null
  await store.fetchTasks(trackId)
}

onMounted(async () => {
  await store.fetchModels()
  await store.fetchTracks()
  await store.fetchTasks(store.selectedTrack)
  await store.fetchRuns()
  // Drop stale selection if it is a legacy mock id (feature-1, etc.)
  if (selectedTask.value && !store.tasks.some(t => t.id === selectedTask.value)) {
    selectedTask.value = null
  }
  try {
    const c = await api.getConstraints()
    constraintsFp.value = c.fingerprint
    constraintsNote.value = c.note
    if (c.opencode) {
      opencodeTools.value = c.opencode
    } else {
      try {
        opencodeTools.value = await api.getOpencodeTools()
      } catch {
        /* optional */
      }
    }
  } catch {
    constraintsNote.value = 'Frozen constraints unavailable (backend offline).'
    try {
      opencodeTools.value = await api.getOpencodeTools()
    } catch {
      /* optional */
    }
  }
})

onUnmounted(() => {
  wsConnections.value.forEach((ws) => {
    try {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    } catch {
      /* ignore */
    }
  })
  wsConnections.value.clear()
})

function toggleModel(modelId: string) {
  if (selectedModels.value.includes(modelId)) {
    selectedModels.value = selectedModels.value.filter(id => id !== modelId)
  } else {
    selectedModels.value = [...selectedModels.value, modelId]
  }
}

/** Extract workspace id `{batch}/{folder}` from absolute workspacePath. */
function workspaceIdFromPath(ws?: string): string | null {
  if (!ws) return null
  const normalized = ws.replace(/\\/g, '/')
  const marker = '/data/workspaces/'
  const idx = normalized.toLowerCase().indexOf(marker)
  if (idx < 0) return null
  let rel = normalized.slice(idx + marker.length)
  if (rel.endsWith('/src')) rel = rel.slice(0, -4)
  return rel || null
}

/**
 * Build accurate preview URL (real HTTP + <base>), not srcdoc.
 * Sibling styles.css / app.js then resolve correctly.
 */
async function loadPreview(run: ArenaRun): Promise<{ url?: string; html?: string }> {
  const rel = workspaceIdFromPath(run.workspacePath)

  // 1) Prefer run-scoped HTTP preview (most accurate for CSS/JS)
  if (run.id && !run.id.startsWith('pending-')) {
    let entry = 'index.html'
    if (rel) {
      try {
        const files = await api.listWorkspaceFiles(rel)
        entry =
          files.html_entrypoints?.find(p => /index\.html?$/i.test(p)) ||
          files.html_entrypoints?.[0] ||
          'index.html'
      } catch {
        /* use default index.html */
      }
    }
    return { url: api.runPreviewUrl(run.id, entry) }
  }

  // 2) Workspace-id preview
  if (!rel) return {}
  try {
    const files = await api.listWorkspaceFiles(rel)
    const htmlPath =
      files.html_entrypoints?.find(p => /index\.html?$/i.test(p)) ||
      files.html_entrypoints?.[0]
    if (!htmlPath) return {}
    return { url: api.workspacePreviewUrl(rel, htmlPath) }
  } catch {
    return {}
  }
}

async function startRun() {
  if (!canStart.value) return

  const taskId = selectedTask.value!
  // Reject legacy mock ids (feature-1 / bugfix-1) that do not exist on the API
  const known = store.tasks.some(t => t.id === taskId)
  if (!known) {
    alert(
      `任务不存在: ${taskId}\n请重新选择下方列表中的真实任务（例如 feature-landing-hero、bugfix-null-pointer）。`,
    )
    selectedTask.value = null
    await store.fetchTasks()
    return
  }

  // Shrink config rail so OpenCode dialogue gets the floor
  configCollapsed.value = true
  toolsCollapsed.value = true

  // Optimistic shells so UI never sticks on "Starting…" waiting for HTTP
  matchRuns.value = selectedModels.value.map((modelId, i) => ({
    id: `pending-${Date.now()}-${i}`,
    modelId,
    taskId,
    status: 'running' as const,
    startedAt: new Date().toISOString(),
    agentSteps: [],
  }))
  for (const run of matchRuns.value) {
    panelTab.value[run.id] = 'terminal'
  }

  try {
    // Close any previous live sockets
    wsConnections.value.forEach((ws) => {
      try { ws.close() } catch { /* ignore */ }
    })
    wsConnections.value.clear()

    const result = await store.startFairArena(selectedModels.value, taskId, {
      parallel: parallel.value,
      track: store.selectedTrack,
      pollIntervalMs: 800,
      onSockets: (sockets) => {
        sockets.forEach((ws, i) => {
          const id = matchRuns.value[i]?.id || `ws-${i}`
          wsConnections.value.set(id, ws)
        })
      },
      onUpdate: (liveRuns) => {
        // Preserve preview while streaming agent steps one-by-one
        const prevById = new Map(matchRuns.value.map(r => [r.id, r]))
        matchRuns.value = liveRuns.map((r) => {
          const prev = prevById.get(r.id)
          const prevByModel = matchRuns.value.find(p => p.modelId === r.modelId)
          const html = prev?.previewHtml || prevByModel?.previewHtml
          const url = prev?.previewUrl || prevByModel?.previewUrl
          return {
            ...r,
            ...(html ? { previewHtml: html } : {}),
            ...(url ? { previewUrl: url } : {}),
          }
        })
        for (const run of matchRuns.value) {
          if (!panelTab.value[run.id]) panelTab.value[run.id] = 'terminal'
          // Streaming: stay on OpenCode dialogue; once finished, jump to preview
          if (run.status === 'running' || run.status === 'pending') {
            panelTab.value[run.id] = 'terminal'
          } else if (
            run.status === 'completed'
            || run.status === 'success'
            || run.status === 'failed'
          ) {
            if (panelTab.value[run.id] !== 'page') {
              panelTab.value[run.id] = 'page'
              // Prefetch preview as soon as this model finishes (parallel arena)
              if (!run.previewUrl && !run.previewHtml) {
                void refreshPreview(run)
              }
            }
          }
        }
      },
    }) as {
      arena_id?: string
      constraints_fingerprint?: string
      normalizedRuns?: ArenaRun[]
    }
    lastArenaId.value = result.arena_id || null
    if (result.constraints_fingerprint) {
      constraintsFp.value = result.constraints_fingerprint
    }

    matchRuns.value = result.normalizedRuns?.length
      ? result.normalizedRuns.map((r) => {
          const prev = matchRuns.value.find(p => p.id === r.id || p.modelId === r.modelId)
          return {
            ...r,
            ...(prev?.previewHtml ? { previewHtml: prev.previewHtml } : {}),
            ...(prev?.previewUrl ? { previewUrl: prev.previewUrl } : {}),
          }
        })
      : store.runs.slice(-selectedModels.value.length)

    // Load accurate HTTP preview URL (CSS/JS relative paths work)
    await Promise.all(
      matchRuns.value.map(async (run, i) => {
        const prev = await loadPreview(run)
        if (prev.url || prev.html) {
          matchRuns.value[i] = {
            ...matchRuns.value[i],
            ...(prev.url ? { previewUrl: prev.url } : {}),
            ...(prev.html ? { previewHtml: prev.html } : {}),
          }
        }
      }),
    )

    // Match finished → jump each panel to page preview
    for (const run of matchRuns.value) {
      if (run.status === 'completed' || run.status === 'success' || run.status === 'failed') {
        panelTab.value[run.id] = 'page'
      } else {
        panelTab.value[run.id] = panelTab.value[run.id] || 'terminal'
      }
    }
  } catch (err) {
    console.error('Failed to start arena:', err)
    matchRuns.value = matchRuns.value.map(r => ({
      ...r,
      status: 'failed' as const,
      error: err instanceof Error ? err.message : 'Failed to start arena',
    }))
    alert(err instanceof Error ? err.message : 'Failed to start arena')
  }
}

function setTab(runId: string, tab: 'terminal' | 'page') {
  panelTab.value[runId] = tab
  if (tab === 'page') {
    const run = matchRuns.value.find(r => r.id === runId)
    if (run && !run.previewUrl) void refreshPreview(run)
  }
}

async function refreshPreview(run: ArenaRun) {
  const prev = await loadPreview(run)
  const i = matchRuns.value.findIndex(r => r.id === run.id)
  if (i < 0) return
  // Cache-bust iframe when refreshing
  const url = prev.url ? `${prev.url}${prev.url.includes('?') ? '&' : '?'}t=${Date.now()}` : undefined
  matchRuns.value[i] = {
    ...matchRuns.value[i],
    ...(url ? { previewUrl: url } : {}),
    ...(prev.html ? { previewHtml: prev.html } : {}),
  }
}

function isStubHtml(html: string): boolean {
  const h = html.toLowerCase()
  if (html.length < 700) return true
  return h.includes('scaffold only') || h.includes('implement the pricing') || h.includes('todo: implement')
}

const statusColor: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-400',
  running: 'bg-[#ff5c33]/12 text-[#ff8a66]',
  completed: 'bg-[#3dd6c6]/12 text-[#3dd6c6]',
  failed: 'bg-[#ff4d6d]/12 text-[#ff4d6d]',
  success: 'bg-[#3dd6c6]/12 text-[#3dd6c6]',
}

function formatDuration(seconds?: number): string {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return secs > 0 ? `${mins}m ${secs.toFixed(0)}s` : `${mins}m`
}

function formatTokenCount(n?: number | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return Number(n).toLocaleString()
}

function tokenSum(run: ArenaRun): number | undefined {
  const a = run.inputTokens
  const b = run.outputTokens
  if (a == null && b == null) return undefined
  return (a || 0) + (b || 0)
}
</script>

<template>
  <div class="min-h-screen py-16 md:py-20 px-5 md:px-8">
    <div class="max-w-[1480px] mx-auto">
      <div class="mb-10 max-w-3xl">
        <div class="eyebrow mb-3">Duel floor</div>
        <h1 class="display-title text-4xl md:text-6xl mb-4">
          <span class="gradient-text">{{ t('arena.title') }}</span>
        </h1>
        <p class="text-[#9a9488] text-lg leading-relaxed">
          {{ t('arena.subtitle') }}
        </p>
      </div>

      <!-- Protocol note: compact strip while dueling -->
      <div
        v-if="!duelActive || !configCollapsed"
        class="mb-6 p-5 glass-card text-sm transition-all duration-500"
      >
        <div class="font-display font-bold text-[#ff8a66] mb-1">{{ t('arena.singleVariable') }}</div>
        <p class="text-[#9a9488]">{{ constraintsNote || t('arena.singleVariableHint') }}</p>
        <p v-if="constraintsFp" class="mt-2 font-mono text-[11px] text-[#7a7368] break-all">
          fingerprint: {{ constraintsFp }}
        </p>
        <p v-if="lastArenaId" class="mt-1 font-mono text-[11px] text-[#3dd6c6]/90">
          arena: {{ lastArenaId }}
        </p>
      </div>

      <!-- Official OpenCode tools: collapsible when duel active -->
      <div
        v-if="opencodeTools && (!duelActive || !toolsCollapsed)"
        class="mb-6 p-5 glass-card text-sm transition-all duration-500"
      >
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <div class="font-display font-bold text-[#f3efe6]">{{ t('arena.opencodeTools') }}</div>
          <span class="text-[11px] px-2 py-0.5 rounded-full bg-[#3dd6c6]/15 text-[#3dd6c6] border border-[#3dd6c6]/25">
            {{ t('arena.opencodeToolsEnabled', { n: opencodeTools.enabled_count }) }}
          </span>
          <span
            v-if="opencodeTools.denied_count"
            class="text-[11px] px-2 py-0.5 rounded-full bg-[#ff4d6d]/15 text-[#ff4d6d] border border-[#ff4d6d]/25"
          >
            {{ t('arena.opencodeToolsDenied', { n: opencodeTools.denied_count }) }}
          </span>
          <a
            v-if="opencodeTools.docs"
            :href="opencodeTools.docs"
            target="_blank"
            rel="noopener"
            class="text-[11px] text-[#ff8a66]/80 hover:text-[#ff8a66]"
          >
            opencode.ai/docs/tools ↗
          </a>
          <button
            v-if="duelActive"
            type="button"
            class="ml-auto text-[11px] font-mono text-[#7a7368] hover:text-[#ff8a66]"
            @click="toolsCollapsed = true"
          >
            {{ t('arena.collapse') }}
          </button>
        </div>
        <p class="text-[#9a9488] text-xs mb-3">
          {{ opencodeTools.note || t('arena.opencodeToolsHint') }}
        </p>
        <div class="space-y-3">
          <div v-for="[cat, tools] in toolsByCategory" :key="cat">
            <div class="text-[10px] uppercase tracking-[0.16em] text-[#7a7368] mb-1.5 font-mono">
              {{ cat }}
            </div>
            <div class="flex flex-wrap gap-1.5">
              <div
                v-for="tool in tools"
                :key="tool.id"
                class="group relative px-2.5 py-1 rounded-md border text-[11px] font-mono cursor-default transition-colors"
                :class="tool.default === 'deny'
                  ? 'border-[#ff4d6d]/30 bg-[#ff4d6d]/10 text-[#ff8a9e]'
                  : 'border-[#ff5c33]/25 bg-[#ff5c33]/10 text-[#f3efe6]'"
                :title="tool.description + (tool.arena_note ? ' — ' + tool.arena_note : '')"
              >
                <span class="font-semibold">{{ tool.name }}</span>
                <span
                  class="ml-1.5 text-[10px] opacity-70"
                  :class="tool.default === 'deny' ? 'text-[#ff4d6d]' : 'text-[#3dd6c6]'"
                >
                  {{ tool.default === 'deny' ? t('arena.toolDeny') : t('arena.toolAllow') }}
                </span>
                <span
                  v-if="tool.experimental"
                  class="ml-1 text-[9px] text-[#e8c547]/80"
                >exp</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <button
        v-else-if="opencodeTools && duelActive && toolsCollapsed"
        type="button"
        class="mb-4 text-[11px] font-mono text-[#7a7368] hover:text-[#ff8a66] transition-colors"
        @click="toolsCollapsed = false"
      >
        {{ t('arena.showTools') }} · {{ opencodeTools.enabled_count }} tools
      </button>

      <div v-if="store.error" class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        {{ store.error }}
      </div>

      <!-- Compact config strip when duel is active -->
      <transition
        enter-active-class="transition-all duration-400 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-250 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="configCollapsed && duelActive"
          class="mb-5 glass-card px-4 py-3 flex flex-wrap items-center gap-3"
        >
          <div class="font-display font-bold text-sm text-[#f3efe6] shrink-0">
            {{ t('arena.configuration') }}
          </div>
          <span class="hidden sm:inline w-px h-4 bg-white/10" />
          <div class="flex flex-wrap items-center gap-2 text-[11px] font-mono min-w-0 flex-1">
            <span
              class="px-2 py-0.5 rounded-md border border-[#ff5c33]/30 bg-[#ff5c33]/10 text-[#ff8a66]"
              :title="t('arena.trackHint')"
            >
              {{ t('tracks.label') }}:
              {{ selectedTrackMeta ? trackLabel(selectedTrackMeta) : store.selectedTrack }}
            </span>
            <span class="px-2 py-0.5 rounded-md border border-white/10 text-[#b8b0a2] truncate max-w-[14rem]">
              {{ selectedTaskMeta?.name || selectedTask || '—' }}
            </span>
            <span
              v-for="(name, i) in selectedModelNames"
              :key="name + i"
              class="px-2 py-0.5 rounded-md border border-white/10 text-[#9a9488]"
            >
              {{ name }}
            </span>
            <span
              v-if="store.isRunning"
              class="px-2 py-0.5 rounded-md border border-[#ff5c33]/25 text-[#ff8a66] animate-pulse"
            >
              {{ t('arena.running') }}
            </span>
          </div>
          <button
            type="button"
            class="btn-secondary !py-1.5 !px-3 !text-xs shrink-0"
            :disabled="store.isRunning"
            @click="expandConfig"
          >
            {{ t('arena.expandConfig') }}
          </button>
        </div>
      </transition>

      <div
        class="grid gap-6 transition-all duration-500"
        :class="configCollapsed && duelActive ? 'lg:grid-cols-1' : 'lg:grid-cols-12'"
      >
        <!-- Config sidebar (full form) -->
        <div
          v-show="!(configCollapsed && duelActive)"
          class="transition-all duration-500"
          :class="configCollapsed && duelActive ? 'lg:col-span-0' : 'lg:col-span-3'"
        >
          <div class="glass-card p-5 sticky top-20">
            <div class="flex items-center justify-between gap-2 mb-4">
              <h2 class="text-lg font-display font-bold tracking-tight">{{ t('arena.configuration') }}</h2>
              <button
                v-if="duelActive"
                type="button"
                class="text-[11px] font-mono text-[#7a7368] hover:text-[#ff8a66]"
                @click="collapseConfig"
              >
                {{ t('arena.collapse') }}
              </button>
            </div>

            <!-- Track selector: partitions task pool only; tools stay frozen -->
            <div class="mb-5">
              <label class="block text-sm font-medium text-kimi-muted mb-1">{{ t('tracks.label') }}</label>
              <p class="text-[11px] text-kimi-muted mb-2 leading-snug">{{ t('arena.trackHint') }}</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="tr in store.tracks.filter(x => x.enabled || x.beta)"
                  :key="tr.id"
                  type="button"
                  class="px-2.5 py-1.5 rounded-lg text-xs border font-medium transition-colors"
                  :class="[
                    store.selectedTrack === tr.id
                      ? 'border-[#ff5c33]/50 bg-[#ff5c33]/15 text-[#ff8a66]'
                      : 'border-kimi-border bg-kimi-surface text-kimi-muted hover:text-kimi-text',
                    !tr.enabled ? 'opacity-60' : '',
                  ]"
                  :disabled="!tr.enabled || store.isRunning"
                  :title="typeof tr.description === 'object' ? (tr.description?.zh || tr.description?.en) : String(tr.description || '')"
                  @click="tr.enabled && selectTrack(tr.id)"
                >
                  {{ trackLabel(tr) }}
                  <span v-if="tr.beta" class="ml-1 text-[9px] text-amber-300/90">beta</span>
                  <span v-if="tr.task_count != null" class="ml-1 opacity-60">{{ tr.task_count }}</span>
                </button>
              </div>
            </div>

            <div class="mb-5">
              <label class="block text-sm font-medium text-kimi-muted mb-2">{{ t('arena.selectModels') }}</label>
              <div class="space-y-2 max-h-48 overflow-y-auto pr-1">
                <button
                  v-for="model in enabledModels"
                  :key="model.id"
                  type="button"
                  class="w-full flex items-center gap-2 p-2.5 rounded-xl border text-left text-sm"
                  :class="selectedModels.includes(model.id)
                    ? 'border-[#ff5c33]/45 bg-[#ff5c33]/8'
                    : 'border-kimi-border bg-kimi-surface'"
                  :disabled="store.isRunning"
                  @click="toggleModel(model.id)"
                >
                  <div
                    class="w-7 h-7 rounded-md flex items-center justify-center text-white text-[10px] font-bold"
                    :style="{ backgroundColor: model.color }"
                  >
                    {{ model.name.charAt(0) }}
                  </div>
                  <span class="truncate">{{ model.name }}</span>
                </button>
              </div>
            </div>

            <div class="mb-5">
              <label class="block text-sm font-medium text-kimi-muted mb-2">
                {{ t('arena.selectTask') }} ({{ store.tasks.length }})
              </label>
              <div v-if="!store.tasks.length" class="text-xs text-kimi-muted py-3 text-center">
                {{ t('tracks.empty') }}
              </div>
              <div v-else class="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                <button
                  v-for="task in store.tasks"
                  :key="task.id"
                  type="button"
                  class="w-full p-2.5 rounded-xl border text-left text-sm"
                  :class="selectedTask === task.id
                    ? 'border-[#ff5c33]/45 bg-[#ff5c33]/8'
                    : 'border-kimi-border bg-kimi-surface'"
                  :disabled="store.isRunning"
                  @click="selectedTask = task.id"
                >
                  <div class="font-medium truncate">{{ task.name }}</div>
                  <div class="text-[11px] text-kimi-muted">
                    {{ task.language }}
                    <span v-if="task.track" class="text-[#ff8a66]/90"> · {{ task.track }}</span>
                    <span v-if="task.language === 'html'" class="text-cyan-400"> · UI</span>
                  </div>
                </button>
              </div>
            </div>

            <label class="flex items-center gap-2 mb-4 text-sm text-kimi-muted">
              <input v-model="parallel" type="checkbox" class="rounded border-kimi-border" :disabled="store.isRunning" />
              {{ t('arena.parallel') }}
            </label>

            <button
              type="button"
              class="w-full py-3 rounded-xl font-medium"
              :class="canStart ? 'btn-primary' : 'bg-kimi-surface text-kimi-muted cursor-not-allowed'"
              :disabled="!canStart"
              @click="startRun"
            >
              {{ store.isRunning ? t('arena.running') : t('arena.startRun') }}
            </button>
          </div>
        </div>

        <!-- Match board: OpenCode terminals side by side -->
        <div
          class="space-y-4 transition-all duration-500"
          :class="configCollapsed && duelActive ? 'lg:col-span-1' : 'lg:col-span-9'"
        >
          <div v-if="!showMatchBoard && !store.isRunning" class="glass-card p-12 text-center text-kimi-muted">
            <p class="text-base mb-2">{{ t('arena.terminalEmpty') }}</p>
            <p class="text-sm opacity-70">{{ t('arena.terminalEmptyHint') }}</p>
          </div>

          <div v-if="store.isRunning && !showMatchBoard" class="glass-card p-8 text-center">
            <div class="inline-flex items-center gap-3 text-[#ff8a66]">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Starting OpenCode agents…
            </div>
          </div>

          <div v-if="store.isRunning && showMatchBoard" class="mb-3 flex items-center gap-2 text-sm text-[#ff8a66]">
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            OpenCode 过程逐步推送中…（思考 → 工具 → 观察，按步实时显示）
          </div>

          <div v-if="showMatchBoard">
            <h2 class="text-lg font-semibold mb-3 flex items-center gap-2">
              <span class="text-emerald-400 font-mono text-sm">$</span>
              {{ t('arena.matchBoard') }}
              <span class="text-sm font-normal text-kimi-muted">— OpenCode dialogue</span>
            </h2>

            <div
              class="grid gap-4"
              :class="matchRuns.length === 1 ? 'grid-cols-1' : 'md:grid-cols-2'"
            >
              <div
                v-for="run in matchRuns"
                :key="run.id"
                class="glass-card overflow-hidden flex flex-col min-h-[560px]"
              >
                <div class="flex items-center gap-2 px-4 py-3 border-b border-kimi-border/40">
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                    :style="{ backgroundColor: store.getModelById(run.modelId)?.color || '#64748b' }"
                  >
                    {{ store.getModelById(run.modelId)?.name?.charAt(0) || '?' }}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="text-sm font-semibold truncate">
                      {{ store.getModelById(run.modelId)?.name || run.modelId }}
                    </div>
                    <div class="text-[10px] text-kimi-muted">
                      {{
                        run.testResults?.total
                          ? `${run.testResults.passed}/${run.testResults.total} tests`
                          : run.status
                      }}
                      ·
                      <span class="text-sky-300/90" :title="t('arena.inputTokens')">
                        in {{ formatTokenCount(run.inputTokens) }}
                      </span>
                      <span class="text-kimi-muted"> / </span>
                      <span class="text-amber-300/90" :title="t('arena.outputTokens')">
                        out {{ formatTokenCount(run.outputTokens) }}
                      </span>
                      <span class="text-kimi-muted">
                        (Σ {{ formatTokenCount(run.tokensUsed ?? tokenSum(run)) }})
                      </span>
                      · {{ formatDuration(run.duration) }}
                      · {{ run.agentSteps?.length ?? 0 }} steps
                    </div>
                  </div>
                  <span class="text-xs px-2 py-0.5 rounded-full" :class="statusColor[run.status] || statusColor.pending">
                    {{ run.status }}
                  </span>
                </div>

                <div class="flex gap-1 px-3 py-2 border-b border-kimi-border/30 text-xs bg-black/20">
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-lg font-medium"
                    :class="(panelTab[run.id] || 'terminal') === 'terminal'
                      ? 'bg-[#ff5c33]/18 text-[#ff8a66]'
                      : 'text-kimi-muted hover:text-kimi-text'"
                    @click="setTab(run.id, 'terminal')"
                  >
                    {{ t('arena.tabTerminal') }}
                  </button>
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-lg font-medium"
                    :class="panelTab[run.id] === 'page'
                      ? 'bg-[#3dd6c6]/18 text-[#3dd6c6]'
                      : 'text-kimi-muted hover:text-kimi-text'"
                    @click="setTab(run.id, 'page')"
                  >
                    {{ t('arena.tabPage') }}
                  </button>
                </div>

                <!-- DEFAULT: OpenCode terminal dialogue -->
                <OpenCodeTerminal
                  v-if="(panelTab[run.id] || 'terminal') === 'terminal'"
                  class="flex-1"
                  :model-name="store.getModelById(run.modelId)?.name || run.modelId"
                  :model-color="store.getModelById(run.modelId)?.color"
                  :status="run.status"
                  :steps="run.agentSteps"
                  :messages="run.agentMessages"
                  :agent-log="run.agentLog"
                  :error="run.error"
                  :tokens="run.tokensUsed"
                  :input-tokens="run.inputTokens"
                  :output-tokens="run.outputTokens"
                  :duration="run.duration"
                />

                <div v-else class="flex-1 flex flex-col min-h-[420px] bg-kimi-surface/20">
                  <div class="flex items-center gap-2 px-3 py-1.5 border-b border-kimi-border/30 text-[11px] text-kimi-muted bg-black/20">
                    <span>页面预览</span>
                    <a
                      v-if="run.previewUrl"
                      :href="run.previewUrl"
                      target="_blank"
                      rel="noopener"
                      class="ml-auto text-blue-300 hover:text-blue-200"
                    >
                      新窗口打开
                    </a>
                    <button
                      v-if="run.previewUrl"
                      type="button"
                      class="text-blue-300 hover:text-blue-200"
                      @click="refreshPreview(run)"
                    >
                      刷新
                    </button>
                  </div>
                  <div
                    v-if="run.previewHtml && isStubHtml(run.previewHtml)"
                    class="px-3 py-1.5 text-[11px] bg-amber-500/15 text-amber-300"
                  >
                    {{ t('arena.stubWarning') }}
                  </div>
                  <!-- Accurate: real HTTP preview so CSS/JS relative paths resolve -->
                  <iframe
                    v-if="run.previewUrl"
                    class="w-full flex-1 min-h-[400px] bg-white"
                    sandbox="allow-scripts allow-forms allow-modals"
                    :src="run.previewUrl"
                    :title="`preview-${run.modelId}`"
                  />
                  <!-- Fallback legacy srcdoc (no external CSS) -->
                  <iframe
                    v-else-if="run.previewHtml"
                    class="w-full flex-1 min-h-[400px] bg-white"
                    sandbox="allow-scripts allow-forms"
                    :srcdoc="run.previewHtml"
                    :title="`preview-${run.modelId}`"
                  />
                  <div v-else class="p-8 text-center text-sm text-kimi-muted">
                    {{ t('arena.noHtml') }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
