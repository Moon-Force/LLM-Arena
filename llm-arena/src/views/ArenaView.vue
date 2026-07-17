<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import { api } from '@/utils/api'
import type { ArenaRun } from '@/types'

const store = useArenaStore()
const { t } = useI18n()
/** Multi-select for fair single-variable arena (≥2 models). */
const selectedModels = ref<string[]>([])
const selectedTask = ref<string | null>(null)
const parallel = ref(true)
const wsConnections = ref<Map<string, WebSocket>>(new Map())
const constraintsNote = ref('')
const constraintsFp = ref('')
const lastArenaId = ref<string | null>(null)

const canStart = computed(
  () => selectedModels.value.length >= 2 && !!selectedTask.value && !store.isRunning,
)

const enabledModels = computed(() => store.models.filter(m => m.enabled !== false))

onMounted(async () => {
  await store.fetchModels()
  await store.fetchTasks()
  await store.fetchRuns()
  try {
    const c = await api.getConstraints()
    constraintsFp.value = c.fingerprint
    constraintsNote.value = c.note
  } catch {
    constraintsNote.value = 'Frozen constraints unavailable (backend offline).'
  }
})

onUnmounted(() => {
  wsConnections.value.forEach((ws) => {
    if (ws.readyState === WebSocket.OPEN) ws.close()
  })
})

function toggleModel(modelId: string) {
  if (selectedModels.value.includes(modelId)) {
    selectedModels.value = selectedModels.value.filter(id => id !== modelId)
  } else {
    selectedModels.value = [...selectedModels.value, modelId]
  }
}

async function startRun() {
  if (!canStart.value) return

  const missingKey = selectedModels.value
    .map(id => store.getModelById(id))
    .filter(m => {
      if (!m) return false
      const p = store.providers.find(x => x.id === m.provider)
      return p?.requiresApiKey && !m.apiKey
    })

  if (missingKey.length) {
    const names = missingKey.map(m => m!.name).join(', ')
    const proceed = confirm(
      `These models have no UI API key (server .env may still work): ${names}\n\nContinue?`,
    )
    if (!proceed) return
  }

  try {
    const result = await store.startFairArena(selectedModels.value, selectedTask.value!, {
      parallel: parallel.value,
    })
    lastArenaId.value = result.arena_id || null
    if (result.constraints_fingerprint) {
      constraintsFp.value = result.constraints_fingerprint
    }
    for (const run of result.runs || []) {
      const id = (run as { id?: string; run_id?: string }).id
        || (run as { run_id?: string }).run_id
      if (id) subscribeToRun(String(id))
    }
  } catch (err) {
    console.error('Failed to start arena:', err)
    alert(err instanceof Error ? err.message : 'Failed to start arena')
  }
}

function subscribeToRun(runId: string) {
  try {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
    const ws = new WebSocket(`${wsUrl}/runs/${runId}`)
    ws.onopen = () => wsConnections.value.set(runId, ws)
    ws.onmessage = (event) => {
      try {
        updateRunFromWebSocket(JSON.parse(event.data))
      } catch {
        /* ignore */
      }
    }
    ws.onclose = () => wsConnections.value.delete(runId)
  } catch (err) {
    console.error('WebSocket failed:', err)
  }
}

function updateRunFromWebSocket(data: Partial<ArenaRun> & { id?: string; run_id?: string }) {
  const id = data.id || data.run_id
  if (!id) return
  const index = store.runs.findIndex(r => r.id === id)
  if (index !== -1) {
    store.runs[index] = { ...store.runs[index], ...data, id }
  }
}

async function cancelRun(runId: string) {
  try {
    await store.cancelArenaRun(runId)
  } catch (err) {
    console.error('Failed to cancel run:', err)
  }
}

const statusColor = {
  pending: 'bg-amber-500/10 text-amber-400',
  running: 'bg-blue-500/10 text-blue-400',
  completed: 'bg-emerald-500/10 text-emerald-400',
  failed: 'bg-rose-500/10 text-rose-400',
}

const statusText: Record<string, string> = {
  pending: 'common.pending',
  running: 'common.running',
  completed: 'common.completed',
  failed: 'common.failed',
}

function formatDuration(seconds?: number): string {
  if (!seconds) return '0s'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return secs > 0 ? `${mins}m ${secs.toFixed(0)}s` : `${mins}m`
}
</script>

<template>
  <div class="min-h-screen py-24 px-6">
    <div class="max-w-7xl mx-auto">
      <div class="text-center mb-12">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          <span class="gradient-text">{{ t('arena.title') }}</span>
        </h1>
        <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
          {{ t('arena.subtitle') }}
        </p>
      </div>

      <!-- Single-variable banner -->
      <div class="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm text-kimi-text">
        <div class="font-semibold text-blue-300 mb-1">{{ t('arena.singleVariable') }}</div>
        <p class="text-kimi-muted">{{ constraintsNote || t('arena.singleVariableHint') }}</p>
        <p v-if="constraintsFp" class="mt-2 font-mono text-xs text-kimi-muted break-all">
          fingerprint: {{ constraintsFp }}
        </p>
        <p v-if="lastArenaId" class="mt-1 font-mono text-xs text-emerald-400/80">
          last arena: {{ lastArenaId }}
        </p>
      </div>

      <div v-if="store.error" class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        {{ store.error }}
      </div>

      <div class="grid lg:grid-cols-3 gap-8">
        <div class="lg:col-span-1 space-y-6">
          <div class="glass-card p-6">
            <h2 class="text-lg font-semibold mb-6">{{ t('arena.configuration') }}</h2>

            <!-- Multi model selection -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-kimi-muted mb-1">
                {{ t('arena.selectModels') }}
              </label>
              <p class="text-xs text-kimi-muted mb-3">{{ t('arena.selectModelsHint') }}</p>
              <div class="space-y-2 max-h-72 overflow-y-auto pr-1">
                <button
                  v-for="model in enabledModels"
                  :key="model.id"
                  type="button"
                  :class="[
                    'w-full flex items-center gap-3 p-3 rounded-xl border transition-all duration-200 text-left',
                    selectedModels.includes(model.id)
                      ? 'border-blue-500/50 bg-blue-500/5'
                      : 'border-kimi-border hover:border-kimi-border-hover bg-kimi-surface',
                  ]"
                  @click="toggleModel(model.id)"
                >
                  <div
                    class="w-5 h-5 rounded border flex items-center justify-center flex-shrink-0"
                    :class="selectedModels.includes(model.id) ? 'bg-blue-500 border-blue-500' : 'border-kimi-border'"
                  >
                    <svg v-if="selectedModels.includes(model.id)" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                    :style="{ backgroundColor: model.color }"
                  >
                    {{ model.name.charAt(0) }}
                  </div>
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-kimi-text truncate">{{ model.name }}</div>
                    <div class="text-xs text-kimi-muted">{{ model.provider }} · {{ model.version }}</div>
                  </div>
                </button>
              </div>
              <p class="text-xs text-kimi-muted mt-2">
                {{ t('arena.selectedCount', { n: selectedModels.length }) }}
              </p>
            </div>

            <!-- Task -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-kimi-muted mb-3">{{ t('arena.selectTask') }}</label>
              <div class="space-y-2">
                <button
                  v-for="task in store.tasks"
                  :key="task.id"
                  type="button"
                  :class="[
                    'w-full p-3 rounded-xl border transition-all duration-200 text-left',
                    selectedTask === task.id
                      ? 'border-blue-500/50 bg-blue-500/5'
                      : 'border-kimi-border hover:border-kimi-border-hover bg-kimi-surface',
                  ]"
                  @click="selectedTask = task.id"
                >
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-sm font-medium text-kimi-text">{{ task.name }}</span>
                    <span
                      :class="[
                        'text-xs px-2 py-0.5 rounded-full',
                        task.difficulty === 'easy' ? 'bg-emerald-500/10 text-emerald-400' :
                        task.difficulty === 'medium' ? 'bg-amber-500/10 text-amber-400' :
                        'bg-rose-500/10 text-rose-400'
                      ]"
                    >
                      {{ task.difficulty }}
                    </span>
                  </div>
                  <div class="text-xs text-kimi-muted">{{ task.language }} · {{ task.type }}</div>
                </button>
              </div>
            </div>

            <label class="flex items-center gap-2 mb-6 text-sm text-kimi-muted cursor-pointer">
              <input v-model="parallel" type="checkbox" class="rounded border-kimi-border" />
              {{ t('arena.parallel') }}
            </label>

            <button
              type="button"
              :class="[
                'w-full py-3 rounded-xl font-medium transition-all duration-300 flex items-center justify-center gap-2',
                canStart ? 'btn-primary' : 'bg-kimi-surface text-kimi-muted cursor-not-allowed',
              ]"
              :disabled="!canStart"
              @click="startRun"
            >
              <svg v-if="store.isRunning" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {{ store.isRunning ? t('arena.running') : t('arena.startRun') }}
            </button>
          </div>
        </div>

        <!-- Results -->
        <div class="lg:col-span-2">
          <div class="glass-card p-6">
            <h2 class="text-lg font-semibold mb-6">{{ t('arena.recentRuns') }}</h2>

            <div v-if="store.runs.length === 0" class="text-center py-12">
              <p class="text-kimi-muted">{{ t('arena.noRuns') }}</p>
            </div>

            <div v-else class="space-y-4">
              <div
                v-for="run in [...store.runs].reverse()"
                :key="run.id"
                class="p-4 rounded-xl border border-kimi-border/50 bg-kimi-surface/50"
              >
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                      :style="{ backgroundColor: store.getModelById(run.modelId)?.color || '#64748b' }"
                    >
                      {{ store.getModelById(run.modelId)?.name?.charAt(0) || '?' }}
                    </div>
                    <div>
                      <div class="text-sm font-medium text-kimi-text">
                        {{ store.getModelById(run.modelId)?.name || run.modelId }}
                      </div>
                      <div class="text-xs text-kimi-muted">
                        {{ store.getTaskById(run.taskId)?.name || run.taskId }}
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs px-2 py-1 rounded-full" :class="statusColor[run.status]">
                      {{ t(statusText[run.status] || 'common.pending') }}
                    </span>
                    <button
                      v-if="run.status === 'running'"
                      type="button"
                      class="p-1 rounded-lg text-kimi-muted hover:text-rose-400"
                      @click="cancelRun(run.id)"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                <div v-if="run.testResults" class="grid grid-cols-3 gap-4 pt-3 border-t border-kimi-border/30">
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.passRate') }}</div>
                    <div class="text-sm font-medium text-kimi-text">
                      {{
                        run.testResults.total
                          ? ((run.testResults.passed / run.testResults.total) * 100).toFixed(1)
                          : '—'
                      }}%
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.tokens') }}</div>
                    <div class="text-sm font-medium text-kimi-text">
                      {{ run.tokensUsed?.toLocaleString() ?? '—' }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.duration') }}</div>
                    <div class="text-sm font-medium text-kimi-text">{{ formatDuration(run.duration) }}</div>
                  </div>
                </div>
                <p v-if="run.error" class="mt-2 text-xs text-rose-400">{{ run.error }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
