import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'
import type { Model, ModelProvider, Task, ArenaRun, LeaderboardEntry, LeaderboardType } from '@/types'

// Default providers
const DEFAULT_PROVIDERS: ModelProvider[] = [
  {
    id: 'anthropic',
    name: 'Anthropic',
    requiresApiKey: true,
    supportsBaseUrl: false,
    models: ['claude-3-opus-20240229', 'claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
  },
  {
    id: 'openai',
    name: 'OpenAI',
    requiresApiKey: true,
    supportsBaseUrl: true,
    defaultBaseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  },
  {
    id: 'google',
    name: 'Google',
    requiresApiKey: true,
    supportsBaseUrl: false,
    models: ['gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    requiresApiKey: true,
    supportsBaseUrl: true,
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-coder'],
  },
  {
    id: 'mimo',
    name: 'Xiaomi MiMo',
    requiresApiKey: true,
    supportsBaseUrl: true,
    defaultBaseUrl: 'https://api.xiaomimimo.com/v1',
    models: ['mimo-v2.5-pro', 'mimo-v2-flash', 'mimo-v2-pro'],
  },
  {
    id: 'custom',
    name: 'Custom / Local',
    requiresApiKey: false,
    supportsBaseUrl: true,
    models: [],
  },
]

// Default built-in models
const DEFAULT_MODELS: Model[] = [
  {
    id: 'claude-opus',
    name: 'Claude Opus',
    provider: 'anthropic',
    version: 'claude-3-opus-20240229',
    description: 'Most capable Claude model for complex tasks',
    color: '#d97757',
    enabled: true,
    custom: false,
  },
  {
    id: 'claude-sonnet',
    name: 'Claude Sonnet',
    provider: 'anthropic',
    version: 'claude-3-5-sonnet-20241022',
    description: 'Balanced performance and speed',
    color: '#d97757',
    enabled: true,
    custom: false,
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'openai',
    version: 'gpt-4o',
    description: 'OpenAI flagship multimodal model',
    color: '#10a37f',
    enabled: true,
    custom: false,
  },
  {
    id: 'gemini-pro',
    name: 'Gemini Pro',
    provider: 'google',
    version: 'gemini-1.5-pro',
    description: 'Google advanced reasoning model',
    color: '#4285f4',
    enabled: true,
    custom: false,
  },
  {
    id: 'deepseek-chat',
    name: 'DeepSeek Chat',
    provider: 'deepseek',
    version: 'deepseek-chat',
    description: 'Efficient open-weight model',
    color: '#4f46e5',
    enabled: true,
    custom: false,
  },
  {
    id: 'mimo-v2.5-pro',
    name: 'MiMo V2.5 Pro',
    provider: 'mimo',
    version: 'mimo-v2.5-pro',
    description: 'Xiaomi MiMo flagship model (OpenAI-compatible)',
    color: '#ff6900',
    baseUrl: 'https://api.xiaomimimo.com/v1',
    enabled: true,
    custom: false,
  },
]

export const useArenaStore = defineStore('arena', () => {
  // State
  const models = ref<Model[]>(loadModelsFromStorage())
  const providers = ref<ModelProvider[]>(DEFAULT_PROVIDERS)
  const tasks = ref<Task[]>([])
  const runs = ref<ArenaRun[]>([])
  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const selectedLeaderboard = ref<LeaderboardType>('overall')

  // Getters
  const getModelById = computed(() => (id: string) =>
    models.value.find(m => m.id === id)
  )

  const getTaskById = computed(() => (id: string) =>
    tasks.value.find(t => t.id === id)
  )

  const enabledModels = computed(() =>
    models.value.filter(m => m.enabled)
  )

  const customModels = computed(() =>
    models.value.filter(m => m.custom)
  )

  const completedRuns = computed(() =>
    runs.value.filter(r => r.status === 'completed')
  )

  const leaderboard = computed<LeaderboardEntry[]>(() => {
    const entries: Record<string, LeaderboardEntry> = {}

    for (const run of completedRuns.value) {
      const model = getModelById.value(run.modelId)
      if (!model) continue

      if (!entries[run.modelId]) {
        entries[run.modelId] = {
          modelId: model.id,
          modelName: model.name,
          modelProvider: model.provider,
          modelColor: model.color,
          runs: 0,
          completedRuns: 0,
          passRate: 0,
          hiddenPassRate: 0,
          avgTokens: 0,
          avgCost: 0,
          avgDuration: 0,
          stability: 0,
          codeQuality: 0,
          safetyScore: 0,
          overallScore: 0,
        }
      }

      const entry = entries[run.modelId]
      entry.runs++

      if (run.status === 'completed') {
        entry.completedRuns++
        entry.avgTokens += run.tokensUsed || 0
        entry.avgCost += run.cost || 0
        entry.avgDuration += run.duration || 0

        if (run.testResults) {
          entry.passRate += run.testResults.passed / run.testResults.total
          entry.hiddenPassRate += run.testResults.hiddenPassed / run.testResults.hiddenTotal
        }
      }
    }

    // Calculate averages
    for (const entry of Object.values(entries)) {
      if (entry.completedRuns > 0) {
        entry.avgTokens /= entry.completedRuns
        entry.avgCost /= entry.completedRuns
        entry.avgDuration /= entry.completedRuns
        entry.passRate = (entry.passRate / entry.completedRuns) * 100
        entry.hiddenPassRate = (entry.hiddenPassRate / entry.completedRuns) * 100
        entry.stability = (entry.completedRuns / entry.runs) * 100
        entry.codeQuality = Math.random() * 30 + 70 // Simulated
        entry.safetyScore = Math.random() * 20 + 80 // Simulated

        // Calculate overall score based on leaderboard type
        switch (selectedLeaderboard.value) {
          case 'overall':
            entry.overallScore =
              entry.hiddenPassRate * 0.4 +
              entry.passRate * 0.2 +
              entry.codeQuality * 0.15 +
              entry.stability * 0.15 +
              entry.safetyScore * 0.1
            break
          case 'accuracy':
            entry.overallScore =
              entry.hiddenPassRate * 0.6 +
              entry.passRate * 0.3 +
              entry.stability * 0.1
            break
          case 'value':
            entry.overallScore =
              (entry.hiddenPassRate * 0.5 + entry.passRate * 0.2) /
              (entry.avgCost * 0.01 + 1)
            break
        }
      }
    }

    return Object.values(entries).sort((a, b) => b.overallScore - a.overallScore)
  })

  // Model Management Actions
  function addModel(model: Omit<Model, 'id' | 'custom'>) {
    const newModel: Model = {
      ...model,
      id: `custom-${Date.now()}`,
      custom: true,
      enabled: true,
    }
    models.value.push(newModel)
    saveModelsToStorage()
    return newModel
  }

  function updateModel(id: string, updates: Partial<Model>) {
    const index = models.value.findIndex(m => m.id === id)
    if (index !== -1) {
      models.value[index] = { ...models.value[index], ...updates }
      saveModelsToStorage()
    }
  }

  function deleteModel(id: string) {
    const index = models.value.findIndex(m => m.id === id)
    if (index !== -1 && models.value[index].custom) {
      models.value.splice(index, 1)
      saveModelsToStorage()
    }
  }

  function toggleModelEnabled(id: string) {
    const model = models.value.find(m => m.id === id)
    if (model) {
      model.enabled = !model.enabled
      saveModelsToStorage()
    }
  }

  function resetToDefaults() {
    models.value = [...DEFAULT_MODELS]
    saveModelsToStorage()
  }

  // Storage helpers
  function saveModelsToStorage() {
    try {
      localStorage.setItem('opencode-models', JSON.stringify(models.value))
    } catch {
      // Ignore storage errors
    }
  }

  function loadModelsFromStorage(): Model[] {
    try {
      const stored = localStorage.getItem('opencode-models')
      if (stored) {
        const parsed = JSON.parse(stored)
        // Merge with defaults to ensure all fields exist
        const storedIds = new Set(parsed.map((m: Model) => m.id))
        const defaults = DEFAULT_MODELS.filter(m => !storedIds.has(m.id))
        return [...parsed, ...defaults]
      }
    } catch {
      // Ignore parse errors
    }
    return [...DEFAULT_MODELS]
  }

  // OpenCode API Actions
  async function fetchModels() {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getModels() as Model[] | { models: Model[] }
      const apiModels: Model[] = Array.isArray(data)
        ? data
        : ((data as { models?: Model[] }).models ?? [])

      // Preserve locally configured apiKey / baseUrl / toggles from localStorage
      const localById = new Map(models.value.map(m => [m.id, m]))

      const mergedFromApi: Model[] = apiModels.map((m) => {
        const local = localById.get(m.id)
        return {
          id: m.id,
          name: m.name ?? local?.name ?? m.id,
          provider: m.provider ?? local?.provider ?? 'custom',
          version: m.version ?? local?.version ?? '',
          description: m.description ?? local?.description ?? '',
          color: local?.color ?? m.color ?? '#3b82f6',
          enabled: local?.enabled ?? true,
          custom: false,
          apiKey: local?.apiKey,
          baseUrl: local?.baseUrl ?? m.baseUrl,
          temperature: local?.temperature ?? m.temperature,
          maxTokens: local?.maxTokens ?? m.maxTokens,
        }
      })

      const apiIds = new Set(mergedFromApi.map(m => m.id))
      const localCustom = models.value.filter(m => m.custom && !apiIds.has(m.id))
      models.value = [...mergedFromApi, ...localCustom]
      saveModelsToStorage()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch models'
      console.error('Failed to fetch models:', err)
      // Keep existing models (including custom ones and stored keys)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTasks() {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getTasks() as Task[] | { tasks: Task[] }
      const list = Array.isArray(data)
        ? data
        : ((data as { tasks?: Task[] }).tasks ?? [])
      // Normalize snake_case fields from backend if present
      tasks.value = list.map((t: Task & { test_cases?: number }) => ({
        ...t,
        testCases: t.testCases ?? t.test_cases ?? 0,
      }))
      if (tasks.value.length === 0) {
        tasks.value = getMockTasks()
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch tasks'
      console.error('Failed to fetch tasks:', err)
      // Fallback to mock data for development
      tasks.value = getMockTasks()
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
      // Prefer explicit options; otherwise use model config from Model Configuration page
      const model = getModelById.value(modelId)
      const runPayload = {
        ...options,
        apiKey: options?.apiKey ?? model?.apiKey,
        provider: options?.provider ?? model?.provider,
        version: options?.version ?? model?.version,
        baseUrl: options?.baseUrl ?? model?.baseUrl,
      }

      const run = await api.startRun(modelId, taskId, runPayload) as ArenaRun
      // Normalize API response shape if backend returns run_id instead of id
      const normalized: ArenaRun = {
        id: (run as ArenaRun).id || (run as unknown as { run_id?: string }).run_id || `run-${Date.now()}`,
        modelId: (run as ArenaRun).modelId || modelId,
        taskId: (run as ArenaRun).taskId || taskId,
        status: (run as ArenaRun).status || 'running',
        startedAt: (run as ArenaRun).startedAt || new Date().toISOString(),
        ...run,
      }
      runs.value.push(normalized)
      return normalized
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to start run'
      console.error('Failed to start run:', err)
      throw err
    } finally {
      isRunning.value = false
    }
  }

  async function cancelArenaRun(runId: string) {
    try {
      await api.cancelRun(runId)
      const index = runs.value.findIndex(r => r.id === runId)
      if (index !== -1) {
        runs.value[index] = { ...runs.value[index], status: 'failed' }
      }
    } catch (err) {
      console.error('Failed to cancel run:', err)
    }
  }

  async function fetchLeaderboardData(type: LeaderboardType = 'overall') {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getLeaderboard(type)
      return data as LeaderboardEntry[]
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch leaderboard'
      console.error('Failed to fetch leaderboard:', err)
      return leaderboard.value
    } finally {
      isLoading.value = false
    }
  }

  function setLeaderboardType(type: LeaderboardType) {
    selectedLeaderboard.value = type
  }

  // Mock data for development
  function getMockTasks(): Task[] {
    return [
      {
        id: 'bugfix-1',
        name: 'Null Pointer Fix',
        description: 'Fix null pointer exception in data processing pipeline',
        language: 'python',
        type: 'bugfix',
        difficulty: 'easy',
        testCases: 5,
      },
      {
        id: 'bugfix-2',
        name: 'Race Condition',
        description: 'Fix race condition in concurrent task scheduler',
        language: 'typescript',
        type: 'bugfix',
        difficulty: 'medium',
        testCases: 8,
      },
      {
        id: 'feature-1',
        name: 'API Rate Limiter',
        description: 'Implement token bucket rate limiter with Redis',
        language: 'python',
        type: 'feature',
        difficulty: 'medium',
        testCases: 10,
      },
      {
        id: 'feature-2',
        name: 'Event Stream Parser',
        description: 'Build SSE parser with backpressure handling',
        language: 'typescript',
        type: 'feature',
        difficulty: 'hard',
        testCases: 12,
      },
    ]
  }

  function startMockRun(modelId: string, taskId: string): ArenaRun {
    const run: ArenaRun = {
      id: `run-${Date.now()}`,
      modelId,
      taskId,
      status: 'running',
      startedAt: new Date().toISOString(),
    }

    runs.value.push(run)
    isRunning.value = true

    // Simulate run completion
    setTimeout(() => {
      const index = runs.value.findIndex(r => r.id === run.id)
      if (index !== -1) {
        runs.value[index] = {
          ...runs.value[index],
          status: 'completed',
          completedAt: new Date().toISOString(),
          duration: Math.random() * 300 + 60,
          tokensUsed: Math.floor(Math.random() * 50000 + 10000),
          cost: Math.random() * 2 + 0.5,
          testResults: {
            total: 10,
            passed: Math.floor(Math.random() * 3 + 7),
            failed: Math.floor(Math.random() * 3),
            hiddenTotal: 5,
            hiddenPassed: Math.floor(Math.random() * 2 + 3),
          },
        }
      }
      isRunning.value = false
    }, 3000)

    return run
  }

  return {
    // State
    models,
    providers,
    tasks,
    runs,
    isLoading,
    isRunning,
    error,
    selectedLeaderboard,
    // Getters
    getModelById,
    getTaskById,
    enabledModels,
    customModels,
    completedRuns,
    leaderboard,
    // Actions
    addModel,
    updateModel,
    deleteModel,
    toggleModelEnabled,
    resetToDefaults,
    fetchModels,
    fetchTasks,
    fetchRuns,
    startArenaRun,
    cancelArenaRun,
    fetchLeaderboardData,
    setLeaderboardType,
  }
})
