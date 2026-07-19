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

const canStart = computed(
  () => selectedModels.value.length >= 2 && !!selectedTask.value && !store.isRunning,
)
const enabledModels = computed(() => store.models.filter(m => m.enabled !== false))
const showMatchBoard = computed(() => matchRuns.value.length > 0)

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
          // Keep terminal tab focused while OpenCode is streaming
          if (run.status === 'running' || run.status === 'pending') {
            panelTab.value[run.id] = 'terminal'
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

    // Default tab = terminal (OpenCode dialogue)
    for (const run of matchRuns.value) {
      panelTab.value[run.id] = 'terminal'
    }

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
  running: 'bg-blue-500/10 text-blue-400',
  completed: 'bg-emerald-500/10 text-emerald-400',
  failed: 'bg-rose-500/10 text-rose-400',
  success: 'bg-emerald-500/10 text-emerald-400',
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
  <div class="min-h-screen py-24 px-6">
    <div class="max-w-[1600px] mx-auto">
      <div class="text-center mb-10">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          <span class="gradient-text">{{ t('arena.title') }}</span>
        </h1>
        <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
          {{ t('arena.subtitle') }}
        </p>
      </div>

      <div class="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm">
        <div class="font-semibold text-blue-300 mb-1">{{ t('arena.singleVariable') }}</div>
        <p class="text-kimi-muted">{{ constraintsNote || t('arena.singleVariableHint') }}</p>
        <p v-if="constraintsFp" class="mt-2 font-mono text-xs text-kimi-muted break-all">
          fingerprint: {{ constraintsFp }}
        </p>
        <p v-if="lastArenaId" class="mt-1 font-mono text-xs text-emerald-400/80">
          arena: {{ lastArenaId }}
        </p>
      </div>

      <!-- Official OpenCode tools (frozen for all contestants) -->
      <div
        v-if="opencodeTools"
        class="mb-6 p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 text-sm"
      >
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <div class="font-semibold text-violet-200">{{ t('arena.opencodeTools') }}</div>
          <span class="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">
            {{ t('arena.opencodeToolsEnabled', { n: opencodeTools.enabled_count }) }}
          </span>
          <span
            v-if="opencodeTools.denied_count"
            class="text-[11px] px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300"
          >
            {{ t('arena.opencodeToolsDenied', { n: opencodeTools.denied_count }) }}
          </span>
          <a
            v-if="opencodeTools.docs"
            :href="opencodeTools.docs"
            target="_blank"
            rel="noopener"
            class="ml-auto text-[11px] text-violet-300/80 hover:text-violet-200"
          >
            opencode.ai/docs/tools ↗
          </a>
        </div>
        <p class="text-kimi-muted text-xs mb-3">
          {{ opencodeTools.note || t('arena.opencodeToolsHint') }}
        </p>
        <div class="space-y-3">
          <div v-for="[cat, tools] in toolsByCategory" :key="cat">
            <div class="text-[10px] uppercase tracking-wider text-kimi-muted mb-1.5 font-mono">
              {{ cat }}
            </div>
            <div class="flex flex-wrap gap-1.5">
              <div
                v-for="tool in tools"
                :key="tool.id"
                class="group relative px-2.5 py-1 rounded-lg border text-[11px] font-mono cursor-default"
                :class="tool.default === 'deny'
                  ? 'border-rose-500/30 bg-rose-500/10 text-rose-300/90'
                  : 'border-violet-500/25 bg-violet-500/10 text-violet-100'"
                :title="tool.description + (tool.arena_note ? ' — ' + tool.arena_note : '')"
              >
                <span class="font-semibold">{{ tool.name }}</span>
                <span
                  class="ml-1.5 text-[10px] opacity-70"
                  :class="tool.default === 'deny' ? 'text-rose-300' : 'text-emerald-300'"
                >
                  {{ tool.default === 'deny' ? t('arena.toolDeny') : t('arena.toolAllow') }}
                </span>
                <span
                  v-if="tool.experimental"
                  class="ml-1 text-[9px] text-amber-300/80"
                >exp</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="store.error" class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        {{ store.error }}
      </div>

      <div class="grid lg:grid-cols-12 gap-6">
        <!-- Config sidebar -->
        <div class="lg:col-span-3">
          <div class="glass-card p-5 sticky top-20">
            <h2 class="text-lg font-semibold mb-4">{{ t('arena.configuration') }}</h2>

            <!-- Track selector: partitions task pool only; tools stay frozen -->
            <div class="mb-5">
              <label class="block text-sm font-medium text-kimi-muted mb-2">{{ t('tracks.label') }}</label>
              <p class="text-[11px] text-kimi-muted mb-2">{{ t('arena.trackHint') }}</p>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="tr in store.tracks.filter(x => x.enabled || x.beta)"
                  :key="tr.id"
                  type="button"
                  class="px-2.5 py-1.5 rounded-lg text-xs border font-medium transition-colors"
                  :class="[
                    store.selectedTrack === tr.id
                      ? 'border-violet-500/50 bg-violet-500/15 text-violet-200'
                      : 'border-kimi-border bg-kimi-surface text-kimi-muted hover:text-kimi-text',
                    !tr.enabled ? 'opacity-60' : '',
                  ]"
                  :disabled="!tr.enabled"
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
                    ? 'border-blue-500/50 bg-blue-500/5'
                    : 'border-kimi-border bg-kimi-surface'"
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
                    ? 'border-blue-500/50 bg-blue-500/5'
                    : 'border-kimi-border bg-kimi-surface'"
                  @click="selectedTask = task.id"
                >
                  <div class="font-medium truncate">{{ task.name }}</div>
                  <div class="text-[11px] text-kimi-muted">
                    {{ task.language }}
                    <span v-if="task.track" class="text-violet-300/90"> · {{ task.track }}</span>
                    <span v-if="task.language === 'html'" class="text-cyan-400"> · UI</span>
                  </div>
                </button>
              </div>
            </div>

            <label class="flex items-center gap-2 mb-4 text-sm text-kimi-muted">
              <input v-model="parallel" type="checkbox" class="rounded border-kimi-border" />
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
        <div class="lg:col-span-9 space-y-4">
          <div v-if="!showMatchBoard && !store.isRunning" class="glass-card p-12 text-center text-kimi-muted">
            <p class="text-base mb-2">{{ t('arena.terminalEmpty') }}</p>
            <p class="text-sm opacity-70">{{ t('arena.terminalEmptyHint') }}</p>
          </div>

          <div v-if="store.isRunning && !showMatchBoard" class="glass-card p-8 text-center">
            <div class="inline-flex items-center gap-3 text-blue-300">
              <svg class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Starting OpenCode agents…
            </div>
          </div>

          <div v-if="store.isRunning && showMatchBoard" class="mb-3 flex items-center gap-2 text-sm text-blue-300">
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
                      ? 'bg-violet-500/20 text-violet-200'
                      : 'text-kimi-muted hover:text-kimi-text'"
                    @click="setTab(run.id, 'terminal')"
                  >
                    {{ t('arena.tabTerminal') }}
                  </button>
                  <button
                    type="button"
                    class="px-3 py-1.5 rounded-lg font-medium"
                    :class="panelTab[run.id] === 'page'
                      ? 'bg-emerald-500/20 text-emerald-200'
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
