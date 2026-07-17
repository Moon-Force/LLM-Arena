<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import type { ArenaRun } from '@/types'

const store = useArenaStore()
const { t } = useI18n()
const selectedModel = ref<string | null>(null)
const selectedTask = ref<string | null>(null)
const wsConnections = ref<Map<string, WebSocket>>(new Map())

const canStart = computed(() => selectedModel.value && selectedTask.value && !store.isRunning)

// Load data on mount
onMounted(async () => {
  await store.fetchModels()
  await store.fetchTasks()
  await store.fetchRuns()
})

onUnmounted(() => {
  // Close all WebSocket connections
  wsConnections.value.forEach((ws) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.close()
    }
  })
})

async function startRun() {
  if (!canStart.value) return

  const model = store.getModelById(selectedModel.value!)
  const provider = store.providers.find(p => p.id === model?.provider)
  // Soft check: warn if UI has no key (backend may still use server env)
  if (provider?.requiresApiKey && !model?.apiKey) {
    const proceed = confirm(
      `Model "${model?.name}" has no API key in Model Configuration.\n\n` +
      `Open /models to set a key, or continue if the server has an environment key configured.`,
    )
    if (!proceed) return
  }

  try {
    // Store attaches model.apiKey / provider / version / baseUrl automatically
    const run = await store.startArenaRun(selectedModel.value!, selectedTask.value!, {
      maxSteps: 100,
      timeout: 300,
    })

    // Subscribe to real-time updates via WebSocket
    if (run && run.id) {
      subscribeToRun(run.id)
    }
  } catch (err) {
    console.error('Failed to start run:', err)
    const message = err instanceof Error ? err.message : 'Failed to start run'
    alert(message)
  }
}

function subscribeToRun(runId: string) {
  try {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
    const ws = new WebSocket(`${wsUrl}/runs/${runId}`)

    ws.onopen = () => {
      console.log(`WebSocket connected for run ${runId}`)
      wsConnections.value.set(runId, ws)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        updateRunFromWebSocket(data)
      } catch {
        console.log('WebSocket message:', event.data)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      wsConnections.value.delete(runId)
    }
  } catch (err) {
    console.error('Failed to connect WebSocket:', err)
  }
}

function updateRunFromWebSocket(data: Partial<ArenaRun> & { id: string }) {
  const index = store.runs.findIndex(r => r.id === data.id)
  if (index !== -1) {
    store.runs[index] = { ...store.runs[index], ...data }
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

// Format duration
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
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl md:text-5xl font-bold mb-4">
          <span class="gradient-text">{{ t('arena.title') }}</span>
        </h1>
        <p class="text-kimi-muted text-lg max-w-2xl mx-auto">
          {{ t('arena.subtitle') }}
        </p>
      </div>

      <!-- Error Alert -->
      <div v-if="store.error" class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75a.75.75 0 100-1.5.75.75 0 000 1.5z" />
          </svg>
          <span>{{ store.error }}</span>
        </div>
      </div>

      <div class="grid lg:grid-cols-3 gap-8">
        <!-- Configuration Panel -->
        <div class="lg:col-span-1 space-y-6">
          <div class="glass-card p-6">
            <h2 class="text-lg font-semibold mb-6 flex items-center gap-2">
              <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.739-.527c.447-.32 1.06-.236 1.318.197l.547.91c.258.437.177 1.003-.197 1.318l-.739.527c-.35.25-.476.687-.376 1.1.1.414.443.72.876.78l.893.15c.55.09.94.56.94 1.11v1.093c0 .55-.39 1.02-.94 1.11l-.893.15c-.433.06-.776.366-.876.78-.1.413-.026.85.376 1.1l.739.527c.374.315.455.881.197 1.318l-.547.91c-.258.437-.871.52-1.318.197l-.739-.527c-.35-.25-.807-.272-1.205-.108-.396.166-.71.506-.78.93l-.149.894c-.09.542-.56.94-1.11.94h-1.093c-.55 0-1.02-.398-1.11-.94l-.149-.894c-.07-.424-.384-.764-.78-.93-.398-.164-.855-.142-1.205.108l-.739.527c-.447.32-1.06.236-1.318-.197l-.547-.91c-.258-.437-.177-1.003.197-1.318l.739-.527c.35-.25.476-.687.376-1.1-.1-.414-.443-.72-.876-.78l-.893-.15c-.55-.09-.94-.56-.94-1.11v-1.093c0-.55.39-1.02.94-1.11l.893-.15c.433-.06.776-.366.876-.78.1-.413.026-.85-.376-1.1l-.739-.527c-.374-.315-.455-.881-.197-1.318l.547-.91c.258-.437.871-.52 1.318-.197l.739.527c.35.25.807.272 1.205.108.396-.166.71-.506.78-.93l.149-.894z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 100-6 3 3 0 000 6z" />
              </svg>
              {{ t('arena.configuration') }}
            </h2>

            <!-- Loading State -->
            <div v-if="store.isLoading && store.models.length === 0" class="text-center py-8">
              <svg class="animate-spin w-8 h-8 text-blue-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <p class="text-kimi-muted text-sm">Loading models...</p>
            </div>

            <!-- Model Selection -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-kimi-muted mb-3">{{ t('arena.selectModel') }}</label>
              <div class="space-y-2">
                <button
                  v-for="model in store.models"
                  :key="model.id"
                  :class="[
                    'w-full flex items-center gap-3 p-3 rounded-xl border transition-all duration-200 text-left',
                    selectedModel === model.id
                      ? 'border-blue-500/50 bg-blue-500/5'
                      : 'border-kimi-border hover:border-kimi-border-hover bg-kimi-surface',
                  ]"
                  @click="selectedModel = model.id"
                >
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                    :style="{ backgroundColor: model.color }"
                  >
                    {{ model.name.charAt(0) }}
                  </div>
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-kimi-text truncate">{{ model.name }}</div>
                    <div class="text-xs text-kimi-muted">{{ model.provider }}</div>
                  </div>
                </button>
              </div>
            </div>

            <!-- Task Selection -->
            <div class="mb-6">
              <label class="block text-sm font-medium text-kimi-muted mb-3">{{ t('arena.selectTask') }}</label>
              <div class="space-y-2">
                <button
                  v-for="task in store.tasks"
                  :key="task.id"
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

            <!-- Start Button -->
            <button
              :class="[
                'w-full py-3 rounded-xl font-medium transition-all duration-300 flex items-center justify-center gap-2',
                canStart
                  ? 'btn-primary'
                  : 'bg-kimi-surface text-kimi-muted cursor-not-allowed',
              ]"
              :disabled="!canStart"
              @click="startRun"
            >
              <svg v-if="store.isRunning" class="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span v-else>
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
              </span>
              {{ store.isRunning ? t('arena.running') : t('arena.startRun') }}
            </button>
          </div>
        </div>

        <!-- Results Panel -->
        <div class="lg:col-span-2">
          <div class="glass-card p-6">
            <h2 class="text-lg font-semibold mb-6 flex items-center gap-2">
              <svg class="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v4.125c0 .621-.504 1.125-1.125 1.125h-2.25A1.125 1.125 0 013 17.25V13.125zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v8.625c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM18.75 5.25c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v12c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V5.25z" />
              </svg>
              {{ t('arena.recentRuns') }}
            </h2>

            <div v-if="store.runs.length === 0" class="text-center py-12">
              <div class="w-16 h-16 rounded-2xl bg-kimi-surface flex items-center justify-center mx-auto mb-4">
                <svg class="w-8 h-8 text-kimi-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
              </div>
              <p class="text-kimi-muted">{{ t('arena.noRuns') }}</p>
            </div>

            <div v-else class="space-y-4">
              <div
                v-for="run in [...store.runs].reverse()"
                :key="run.id"
                class="p-4 rounded-xl border border-kimi-border/50 bg-kimi-surface/50 hover:bg-kimi-surface transition-colors duration-200"
              >
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div
                      class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                      :style="{ backgroundColor: store.getModelById(run.modelId)?.color }"
                    >
                      {{ store.getModelById(run.modelId)?.name.charAt(0) }}
                    </div>
                    <div>
                      <div class="text-sm font-medium text-kimi-text">{{ store.getModelById(run.modelId)?.name }}</div>
                      <div class="text-xs text-kimi-muted">{{ store.getTaskById(run.taskId)?.name }}</div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      class="text-xs px-2 py-1 rounded-full"
                      :class="statusColor[run.status]"
                    >
                      {{ t(statusText[run.status]) }}
                    </span>
                    <!-- Cancel button for running runs -->
                    <button
                      v-if="run.status === 'running'"
                      class="p-1 rounded-lg text-kimi-muted hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      @click="cancelRun(run.id)"
                      title="Cancel run"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>

                <!-- Progress bar for running runs -->
                <div v-if="run.status === 'running'" class="mb-3">
                  <div class="w-full h-1.5 bg-kimi-surface rounded-full overflow-hidden">
                    <div class="h-full bg-blue-500 rounded-full animate-pulse" style="width: 60%" />
                  </div>
                  <div class="text-xs text-kimi-muted mt-1">Running via OpenCode...</div>
                </div>

                <div v-if="run.testResults" class="grid grid-cols-3 gap-4 pt-3 border-t border-kimi-border/30">
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.passRate') }}</div>
                    <div class="text-sm font-medium text-kimi-text">
                      {{ ((run.testResults.passed / run.testResults.total) * 100).toFixed(1) }}%
                    </div>
                  </div>
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.tokens') }}</div>
                    <div class="text-sm font-medium text-kimi-text">{{ run.tokensUsed?.toLocaleString() }}</div>
                  </div>
                  <div>
                    <div class="text-xs text-kimi-muted mb-1">{{ t('arena.duration') }}</div>
                    <div class="text-sm font-medium text-kimi-text">{{ formatDuration(run.duration) }}</div>
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
