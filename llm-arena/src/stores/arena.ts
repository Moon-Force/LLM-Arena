import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/utils/api'
import type { Model, ModelProvider, Task, ArenaRun, LeaderboardEntry, LeaderboardType, TrackInfo } from '@/types'

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
    models: ['deepseek-v4-pro', 'deepseek-v4-flash'],
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
    id: 'deepseek-v4-pro',
    name: 'DeepSeek V4 Pro',
    provider: 'deepseek',
    version: 'deepseek-v4-pro',
    description: 'DeepSeek-V4-Pro flagship (agentic coding, 1M context)',
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
  const tracks = ref<TrackInfo[]>([])
  const selectedTrack = ref<string>('frontend')
  const runs = ref<ArenaRun[]>([])
  const isLoading = ref(false)
  const isRunning = ref(false)
  const error = ref<string | null>(null)
  const selectedLeaderboard = ref<LeaderboardType>('overall')
  const selectedLeaderboardTrack = ref<string>('all')

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
    const track = selectedLeaderboardTrack.value

    for (const run of completedRuns.value) {
      // Single-variable scores only comparable within the same track
      if (track && track !== 'all') {
        const runTrack = run.track || getTaskById.value(run.taskId)?.track
        if (runTrack !== track) continue
      }
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
        // No simulated quality/safety — only real metrics
        entry.codeQuality = 0
        entry.safetyScore = 0

        // Calculate overall score based on leaderboard type (real metrics only)
        switch (selectedLeaderboard.value) {
          case 'overall':
            entry.overallScore =
              (entry.hiddenPassRate || entry.passRate) * 0.5 +
              entry.passRate * 0.3 +
              entry.stability * 0.2
            break
          case 'accuracy':
            entry.overallScore =
              (entry.hiddenPassRate || entry.passRate) * 0.6 +
              entry.passRate * 0.3 +
              entry.stability * 0.1
            break
          case 'value':
            entry.overallScore =
              (entry.passRate * 0.7 + entry.stability * 0.3) /
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

  /** Apply .env secrets onto models (by model id or provider). */
  function applySecretsToModels(secrets: {
    models?: Record<string, { api_key?: string; base_url?: string; provider?: string }>
    providers?: Record<string, { api_key?: string; base_url?: string; apiKey?: string; baseUrl?: string }>
  }) {
    const byModel = secrets.models || {}
    const byProvider = secrets.providers || {}
    models.value = models.value.map((m) => {
      const fromModel = byModel[m.id]
      const fromProv = byProvider[m.provider]
      const apiKey =
        (fromModel?.api_key || fromProv?.api_key || fromProv?.apiKey || '').trim() || m.apiKey
      const baseUrl =
        (fromModel?.base_url || fromProv?.base_url || fromProv?.baseUrl || '').trim() || m.baseUrl
      return { ...m, apiKey: apiKey || undefined, baseUrl: baseUrl || undefined }
    })
    saveModelsToStorage()
  }

  /** .env → frontend (localStorage models) */
  async function syncKeysFromEnv() {
    const secrets = await api.getSecrets()
    applySecretsToModels(secrets)
    return secrets
  }

  /** frontend → .env (one row per provider used by models that have keys) */
  async function syncKeysToEnv() {
    const byProvider = new Map<string, { provider: string; api_key?: string; base_url?: string }>()
    for (const m of models.value) {
      if (!m.provider) continue
      const prev = byProvider.get(m.provider) || { provider: m.provider }
      // Prefer non-empty model key; last non-empty wins per provider
      if (m.apiKey) prev.api_key = m.apiKey
      if (m.baseUrl) prev.base_url = m.baseUrl
      byProvider.set(m.provider, prev)
    }
    const updates = [...byProvider.values()].filter(u => u.api_key || u.base_url)
    if (!updates.length) {
      throw new Error('No API keys in UI to write to .env')
    }
    return api.putSecrets(updates)
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
        let parsed = JSON.parse(stored) as Model[]
        // Migrate legacy deepseek-chat → deepseek-v4-pro (keep API key)
        const legacy = parsed.find(m => m.id === 'deepseek-chat')
        if (legacy) {
          parsed = parsed.filter(m => m.id !== 'deepseek-chat')
          if (!parsed.some(m => m.id === 'deepseek-v4-pro')) {
            parsed.push({
              ...legacy,
              id: 'deepseek-v4-pro',
              name: 'DeepSeek V4 Pro',
              version: 'deepseek-v4-pro',
              description: 'DeepSeek-V4-Pro flagship (agentic coding, 1M context)',
            })
          } else {
            const idx = parsed.findIndex(m => m.id === 'deepseek-v4-pro')
            if (idx !== -1 && legacy.apiKey && !parsed[idx].apiKey) {
              parsed[idx] = { ...parsed[idx], apiKey: legacy.apiKey, baseUrl: legacy.baseUrl ?? parsed[idx].baseUrl }
            }
          }
        }
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

      // Prefer localStorage keys, then leave empty (filled by syncKeysFromEnv)
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
          baseUrl: local?.baseUrl ?? (m as Model).baseUrl,
          temperature: local?.temperature ?? m.temperature,
          maxTokens: local?.maxTokens ?? m.maxTokens,
        }
      })

      const apiIds = new Set(mergedFromApi.map(m => m.id))
      const localCustom = models.value.filter(m => m.custom && !apiIds.has(m.id))
      models.value = [...mergedFromApi, ...localCustom]
      saveModelsToStorage()
      // Auto pull keys from .env so UI matches server
      try {
        await syncKeysFromEnv()
      } catch (e) {
        console.warn('Could not sync keys from .env:', e)
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch models'
      console.error('Failed to fetch models:', err)
      // Keep existing models (including custom ones and stored keys)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchTracks() {
    try {
      const data = await api.getTracks()
      tracks.value = (data.tracks || []) as TrackInfo[]
      // Prefer an enabled track that has tasks
      const enabled = tracks.value.filter(t => t.enabled)
      const withTasks = enabled.find(t => (t.task_count || 0) > 0) || enabled[0]
      if (withTasks && !tracks.value.some(t => t.id === selectedTrack.value && t.enabled)) {
        selectedTrack.value = withTasks.id
      }
    } catch (err) {
      console.warn('Failed to fetch tracks:', err)
      tracks.value = [
        { id: 'bugfix', order: 2, enabled: true, name: { zh: 'Bug 修复', en: 'Bugfix' } },
        { id: 'feature', order: 3, enabled: true, name: { zh: '功能实现', en: 'Feature' } },
        { id: 'frontend', order: 4, enabled: true, name: { zh: '前端 / UI', en: 'Frontend' } },
      ]
    }
  }

  async function fetchTasks(track?: string) {
    isLoading.value = true
    error.value = null
    const trackId = track ?? selectedTrack.value
    try {
      const data = await api.getTasks({ track: trackId }) as Task[] | { tasks: Task[] }
      const list = Array.isArray(data)
        ? data
        : ((data as { tasks?: Task[] }).tasks ?? [])
      // Normalize snake_case fields from backend if present
      tasks.value = list.map((t: Task & { test_cases?: number; trackId?: string }) => ({
        ...t,
        testCases: t.testCases ?? t.test_cases ?? 0,
        track: t.track || t.trackId || trackId,
      }))
      if (tasks.value.length === 0) {
        console.warn('API returned 0 tasks; using offline task catalog (real ids)')
        tasks.value = getMockTasks().filter(
          t => !trackId || trackId === 'all' || t.track === trackId,
        )
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch tasks'
      console.error('Failed to fetch tasks:', err)
      // Same real task ids as backend — never invent feature-1 / bugfix-1
      tasks.value = getMockTasks().filter(
        t => !trackId || trackId === 'all' || t.track === trackId,
      )
    } finally {
      isLoading.value = false
    }
  }

  function setSelectedTrack(track: string) {
    selectedTrack.value = track
  }

  async function fetchRuns(filters?: { modelId?: string; taskId?: string; status?: string }) {
    isLoading.value = true
    error.value = null
    try {
      const data = await api.getRuns(filters) as ArenaRun[] | { runs: Record<string, unknown>[] }
      const list = Array.isArray(data)
        ? data
        : ((data as { runs?: Record<string, unknown>[] }).runs ?? [])
      runs.value = list.map(r =>
        normalizeRun(r as Record<string, unknown>, '', ''),
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch runs'
      console.error('Failed to fetch runs:', err)
    } finally {
      isLoading.value = false
    }
  }

  function normalizeRun(run: Record<string, unknown>, fallbackModelId: string, fallbackTaskId: string): ArenaRun {
    const tr = (run.testResults || run.test_results) as ArenaRun['testResults'] | undefined
    const steps = (run.agentSteps || run.agent_steps) as ArenaRun['agentSteps'] | undefined
    const messages = (run.agentMessages || run.agent_messages) as ArenaRun['agentMessages'] | undefined
    return {
      id: String(run.id || run.run_id || `run-${Date.now()}`),
      modelId: String(run.modelId || run.model_id || fallbackModelId),
      taskId: String(run.taskId || run.task_id || fallbackTaskId),
      track: String(run.track || run.trackId || '') || undefined,
      status: (run.status as ArenaRun['status']) || 'running',
      startedAt: String(run.startedAt || run.started_at || new Date().toISOString()),
      completedAt: run.completedAt || run.completed_at
        ? String(run.completedAt || run.completed_at)
        : undefined,
      duration: (run.duration as number | undefined) ?? undefined,
      tokensUsed: (run.tokensUsed as number | undefined) ?? (run.tokens_used as number | undefined),
      inputTokens: (run.inputTokens as number | undefined) ?? (run.input_tokens as number | undefined),
      outputTokens: (run.outputTokens as number | undefined) ?? (run.output_tokens as number | undefined),
      testResults: tr
        ? {
            total: Number((tr as { total?: number }).total || 0),
            passed: Number((tr as { passed?: number }).passed || 0),
            failed: Number((tr as { failed?: number }).failed || 0),
            hiddenPassed: Number((tr as { hiddenPassed?: number; hidden_passed?: number }).hiddenPassed
              ?? (tr as { hidden_passed?: number }).hidden_passed ?? 0),
            hiddenTotal: Number((tr as { hiddenTotal?: number; hidden_total?: number }).hiddenTotal
              ?? (tr as { hidden_total?: number }).hidden_total ?? 0),
          }
        : undefined,
      error: run.error as string | undefined,
      workspacePath: String(run.workspacePath || run.workspace_path || '') || undefined,
      agentSteps: steps,
      agentMessages: messages,
      agentLog: String(run.agentLog || run.agent_log || '') || undefined,
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
      const runPayload = {
        ...options,
        apiKey: options?.apiKey ?? model?.apiKey,
        provider: options?.provider ?? model?.provider,
        version: options?.version ?? model?.version,
        baseUrl: options?.baseUrl ?? model?.baseUrl,
      }

      const run = await api.startRun(modelId, taskId, runPayload) as Record<string, unknown>
      const normalized = normalizeRun(run, modelId, taskId)
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

  /** Multi-model fair match: same frozen constraints, only model/API differ.
   *  API returns immediately with running shells; live OpenCode steps stream via
   *  WebSocket (preferred) + HTTP poll fallback until all runs finish. */
  async function startFairArena(
    modelIds: string[],
    taskId: string,
    options?: {
      parallel?: boolean
      track?: string
      /** Called whenever run snapshots change (live steps / tools). */
      onUpdate?: (runs: ArenaRun[]) => void
      pollIntervalMs?: number
      /** Optional: receive WebSocket handles for cleanup */
      onSockets?: (sockets: WebSocket[]) => void
    },
  ) {
    if (modelIds.length < 2) {
      throw new Error('Select at least 2 models for a fair arena match')
    }
    isRunning.value = true
    error.value = null
    const sockets: WebSocket[] = []
    try {
      const models = modelIds.map(id => {
        const m = getModelById.value(id)
        if (!m) throw new Error(`Model not found: ${id}`)
        return {
          modelId: m.id,
          provider: m.provider,
          version: m.version,
          apiKey: m.apiKey,
          baseUrl: m.baseUrl,
        }
      })
      const result = await api.startArena({
        taskId,
        track: options?.track || selectedTrack.value,
        models,
        parallel: options?.parallel ?? true,
      }) as {
        arena_id?: string
        runs?: Record<string, unknown>[]
        constraints_fingerprint?: string
        report?: unknown
        status?: string
        live?: boolean
      }

      let newRuns = (result.runs || []).map(r =>
        normalizeRun(r, String(r.model_id || r.modelId || ''), taskId),
      )
      runs.value.push(...newRuns)
      options?.onUpdate?.([...newRuns])

      const applyRunUpdate = (updated: ArenaRun) => {
        const i = newRuns.findIndex(r => r.id === updated.id)
        if (i !== -1) newRuns[i] = updated
        else newRuns.push(updated)
        newRuns = [...newRuns]
        const idx = runs.value.findIndex(x => x.id === updated.id)
        if (idx !== -1) runs.value[idx] = updated
        options?.onUpdate?.([...newRuns])
      }

      // Prefer WebSocket for step-by-step OpenCode process
      for (const run of newRuns) {
        try {
          const ws = api.connectWebSocket(
            run.id,
            (data) => {
              if (!data || typeof data !== 'object') return
              const msg = data as { type?: string; run?: Record<string, unknown> }
              const raw = msg.run || (msg as Record<string, unknown>)
              if (!raw || (!raw.id && !raw.run_id && !raw.model_id && !raw.modelId)) return
              const normalized = normalizeRun(raw, run.modelId, run.taskId)
              applyRunUpdate(normalized)
            },
            (err) => console.warn('[arena] ws error', run.id, err),
          )
          sockets.push(ws)
        } catch (e) {
          console.warn('[arena] ws connect failed', run.id, e)
        }
      }
      options?.onSockets?.(sockets)

      // Live mode: also poll as fallback (Docker / WS glitches)
      const stillRunning = () =>
        newRuns.some(r => r.status === 'running' || r.status === 'pending')

      if (result.live !== false && stillRunning()) {
        const interval = options?.pollIntervalMs ?? 800
        const deadline = Date.now() + 15 * 60 * 1000
        while (stillRunning() && Date.now() < deadline) {
          await new Promise(r => setTimeout(r, interval))
          const refreshed = await Promise.all(
            newRuns.map(async (run) => {
              try {
                const raw = await api.getRun(run.id) as Record<string, unknown>
                return normalizeRun(raw, run.modelId, run.taskId)
              } catch {
                return run
              }
            }),
          )
          // Only emit when something changed (steps / tools / status)
          let changed = false
          const runSig = (r: ArenaRun) => {
            const last = r.agentSteps?.at(-1)
            const toolsDone = last?.tools_completed ?? 0
            const thoughtLen = last?.thought?.length ?? 0
            return [
              r.status,
              r.agentSteps?.length ?? 0,
              r.agentMessages?.length ?? 0,
              r.agentLog?.length ?? 0,
              r.tokensUsed ?? 0,
              r.inputTokens ?? 0,
              r.outputTokens ?? 0,
              toolsDone,
              thoughtLen,
            ].join('|')
          }
          for (let i = 0; i < refreshed.length; i++) {
            if (runSig(newRuns[i]) !== runSig(refreshed[i])) changed = true
          }
          newRuns = refreshed
          for (const r of refreshed) {
            const idx = runs.value.findIndex(x => x.id === r.id)
            if (idx !== -1) runs.value[idx] = r
          }
          if (changed) options?.onUpdate?.([...newRuns])
        }
      }

      return { ...result, normalizedRuns: newRuns }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to start arena'
      console.error('Failed to start fair arena:', err)
      throw err
    } finally {
      for (const ws of sockets) {
        try {
          if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            ws.close()
          }
        } catch {
          /* ignore */
        }
      }
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

  function setLeaderboardTrack(track: string) {
    selectedLeaderboardTrack.value = track
  }

  // Offline fallback — IDs must match backend tasks/ folders (task.json).
  function getMockTasks(): Task[] {
    return [
      {
        id: 'bugfix-null-pointer',
        name: 'Null Pointer Fix',
        description: 'Fix a null pointer exception in a data processing pipeline.',
        language: 'python',
        type: 'bugfix',
        difficulty: 'easy',
        testCases: 5,
        track: 'bugfix',
      },
      {
        id: 'feature-rate-limiter',
        name: 'API Rate Limiter',
        description: 'Implement a token bucket rate limiter with Redis backend.',
        language: 'python',
        type: 'feature',
        difficulty: 'medium',
        testCases: 10,
        track: 'feature',
      },
      {
        id: 'feature-landing-hero',
        name: 'Landing Hero Page',
        description: 'Build a single-file marketing landing page.',
        language: 'html',
        type: 'feature',
        difficulty: 'easy',
        testCases: 8,
        track: 'frontend',
      },
      {
        id: 'feature-todo-app',
        name: 'Interactive Todo App',
        description: 'Implement a small interactive Todo utility.',
        language: 'html',
        type: 'feature',
        difficulty: 'medium',
        testCases: 9,
        track: 'frontend',
      },
      {
        id: 'bugfix-form-a11y',
        name: 'Accessible Contact Form Fix',
        description: 'Fix accessibility issues in a contact form.',
        language: 'html',
        type: 'bugfix',
        difficulty: 'medium',
        testCases: 8,
        track: 'frontend',
      },
      {
        id: 'bugfix-navbar-mobile',
        name: 'Mobile Navbar Layout Fix',
        description: 'Fix a responsive navbar bug for mobile.',
        language: 'html',
        type: 'bugfix',
        difficulty: 'medium',
        testCases: 7,
        track: 'frontend',
      },
      {
        id: 'feature-pricing-toggle',
        name: 'Pricing Page with Billing Toggle',
        description: 'Build a pricing section with plan cards and billing toggle.',
        language: 'html',
        type: 'feature',
        difficulty: 'medium',
        testCases: 8,
        track: 'frontend',
      },
      {
        id: 'feature-saas-landing-pro',
        name: 'SaaS Landing (Aesthetics + Multi-section)',
        description: 'Complex OrbitFlow multi-section SaaS landing with anti-slop aesthetics.',
        language: 'html',
        type: 'feature',
        difficulty: 'hard',
        testCases: 14,
        track: 'frontend',
      },
      {
        id: 'feature-admin-users-table',
        name: 'Admin Users Dashboard',
        description: 'Nimbus admin shell with KPIs, filters, user table, invite modal.',
        language: 'html',
        type: 'feature',
        difficulty: 'hard',
        testCases: 13,
        track: 'frontend',
      },
      {
        id: 'feature-kanban-board',
        name: 'Interactive Kanban Board',
        description: 'Sprint Board with 4 columns, add/move/filter cards.',
        language: 'html',
        type: 'feature',
        difficulty: 'hard',
        testCases: 12,
        track: 'frontend',
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
    tracks,
    selectedTrack,
    runs,
    isLoading,
    isRunning,
    error,
    selectedLeaderboard,
    selectedLeaderboardTrack,
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
    applySecretsToModels,
    syncKeysFromEnv,
    syncKeysToEnv,
    fetchModels,
    fetchTracks,
    fetchTasks,
    setSelectedTrack,
    fetchRuns,
    startArenaRun,
    startFairArena,
    cancelArenaRun,
    fetchLeaderboardData,
    setLeaderboardType,
    setLeaderboardTrack,
  }
})
