import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/utils/api'
import type { Model, Task, ArenaRun, LeaderboardEntry, LeaderboardType } from '@/types'

export const useOpenCodeStore = defineStore('opencode', () => {
  // State
  const models = ref<Model[]>([])
  const tasks = ref<Task[]>([])
  const runs = ref<ArenaRun[]>([])
  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const selectedLeaderboard = ref<LeaderboardType>('overall')
  const systemStatus = ref<{
    healthy: boolean
    version: string
    activeRuns: number
    totalRuns: number
  } | null>(null)

  // Getters
  const getModelById = computed(() => (id: string) =>
    models.value.find(m => m.id === id)
  )

  const getTaskById = computed(() => (id: string) =>
    tasks.value.find(t => t.id === id)
  )

  const completedRuns = computed(() =>
    runs.value.filter(r => r.status === 'completed')
  )

  const activeRuns = computed(() =>
    runs.value.filter(r => r.status === 'running')
  )

  // Actions
  async function fetchModels() {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getModels()
      models.value = data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch models'
      console.error('Failed to fetch models:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTasks() {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getTasks()
      tasks.value = data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch tasks'
      console.error('Failed to fetch tasks:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchRuns(filters?: { modelId?: string; taskId?: string; status?: string }) {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getRuns(filters)
      runs.value = data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch runs'
      console.error('Failed to fetch runs:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function startArenaRun(modelId: string, taskId: string, options?: {
    containerConfig?: Record<string, unknown>
    maxSteps?: number
    timeout?: number
    apiKey?: string
    provider?: string
    version?: string
    baseUrl?: string
  }) {
    isRunning.value = true
    error.value = null
    try {
      const model = getModelById.value(modelId)
      const run = await api.startRun(modelId, taskId, {
        ...options,
        apiKey: options?.apiKey ?? model?.apiKey,
        provider: options?.provider ?? model?.provider,
        version: options?.version ?? model?.version,
        baseUrl: options?.baseUrl ?? model?.baseUrl,
      })
      runs.value.push(run)
      return run
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to start run'
      console.error('Failed to start run:', err)
      throw err
    } finally {
      isRunning.value = false
    }
  }

  async function fetchRun(runId: string) {
    try {
      const run = await api.getRun(runId)
      const index = runs.value.findIndex(r => r.id === runId)
      if (index !== -1) {
        runs.value[index] = run
      }
      return run
    } catch (err) {
      console.error('Failed to fetch run:', err)
      throw err
    }
  }

  async function cancelRun(runId: string) {
    try {
      await api.cancelRun(runId)
      const index = runs.value.findIndex(r => r.id === runId)
      if (index !== -1) {
        runs.value[index] = { ...runs.value[index], status: 'failed' }
      }
    } catch (err) {
      console.error('Failed to cancel run:', err)
      throw err
    }
  }

  async function fetchLeaderboard(type: LeaderboardType = 'overall') {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getLeaderboard(type)
      return data as LeaderboardEntry[]
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch leaderboard'
      console.error('Failed to fetch leaderboard:', err)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function fetchSystemStatus() {
    try {
      const data = await api.getSystemStatus()
      systemStatus.value = data
    } catch (err) {
      console.error('Failed to fetch system status:', err)
    }
  }

  function setLeaderboardType(type: LeaderboardType) {
    selectedLeaderboard.value = type
  }

  // WebSocket for real-time updates
  function subscribeToRun(runId: string, onUpdate: (run: ArenaRun) => void) {
    const ws = api.connectWebSocket(
      runId,
      (data) => {
        if (data && typeof data === 'object') {
          const runData = data as ArenaRun
          const index = runs.value.findIndex(r => r.id === runId)
          if (index !== -1) {
            runs.value[index] = { ...runs.value[index], ...runData }
          }
          onUpdate(runs.value[index])
        }
      },
      (error) => {
        console.error('WebSocket error:', error)
      }
    )

    return ws
  }

  return {
    // State
    models,
    tasks,
    runs,
    isLoading,
    isRunning,
    error,
    selectedLeaderboard,
    systemStatus,

    // Getters
    getModelById,
    getTaskById,
    completedRuns,
    activeRuns,

    // Actions
    fetchModels,
    fetchTasks,
    fetchRuns,
    startArenaRun,
    fetchRun,
    cancelRun,
    fetchLeaderboard,
    fetchSystemStatus,
    setLeaderboardType,
    subscribeToRun,
  }
})
