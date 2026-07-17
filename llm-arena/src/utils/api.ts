// OpenCode API client
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

interface ApiResponse<T> {
  data: T
  success: boolean
  message?: string
}

class OpenCodeApi {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`
      try {
        const body = await response.json()
        if (typeof body?.detail === 'string') {
          detail = body.detail
        } else if (body?.message) {
          detail = body.message
        }
      } catch {
        // ignore JSON parse errors
      }
      throw new Error(detail)
    }

    return response.json()
  }

  // Models
  async getModels() {
    return this.request('/models')
  }

  // Tasks
  async getTasks() {
    return this.request('/tasks')
  }

  // Frozen single-variable constraints
  async getConstraints() {
    return this.request<{
      fingerprint: string
      constraints: Record<string, unknown>
      variable_allowed: string[]
      variable_forbidden: string[]
      note: string
    }>('/constraints')
  }

  // Arena Runs
  async getRuns(params?: { modelId?: string; taskId?: string; status?: string }) {
    const queryParams = new URLSearchParams()
    if (params?.modelId) queryParams.append('model_id', params.modelId)
    if (params?.taskId) queryParams.append('task_id', params.taskId)
    if (params?.status) queryParams.append('status', params.status)

    const query = queryParams.toString()
    return this.request(`/runs${query ? `?${query}` : ''}`)
  }

  async startRun(modelId: string, taskId: string, options?: {
    containerConfig?: Record<string, unknown>
    maxSteps?: number
    timeout?: number
    apiKey?: string
    provider?: string
    version?: string
    baseUrl?: string
  }) {
    return this.request('/runs', {
      method: 'POST',
      body: JSON.stringify({
        model_id: modelId,
        task_id: taskId,
        container_config: options?.containerConfig,
        // max_steps/timeout ignored by server (frozen); kept for compatibility
        max_steps: options?.maxSteps,
        timeout: options?.timeout,
        // Only credentials + identity are variable
        api_key: options?.apiKey,
        provider: options?.provider,
        version: options?.version,
        base_url: options?.baseUrl,
      }),
    })
  }

  /** Multi-model fair arena (requires ≥2 models). */
  async startArena(payload: {
    taskId: string
    models: Array<{
      modelId: string
      provider: string
      version: string
      apiKey?: string
      baseUrl?: string
    }>
    parallel?: boolean
  }) {
    return this.request('/arena', {
      method: 'POST',
      body: JSON.stringify({
        task_id: payload.taskId,
        parallel: payload.parallel ?? true,
        models: payload.models.map(m => ({
          model_id: m.modelId,
          provider: m.provider,
          version: m.version,
          api_key: m.apiKey,
          base_url: m.baseUrl,
        })),
      }),
    })
  }

  async getRun(runId: string) {
    return this.request(`/runs/${runId}`)
  }

  async getRunLogs(runId: string) {
    return this.request(`/runs/${runId}/logs`)
  }

  async getRunDiff(runId: string) {
    return this.request(`/runs/${runId}/diff`)
  }

  async getRunToolCalls(runId: string) {
    return this.request(`/runs/${runId}/tool-calls`)
  }

  async cancelRun(runId: string) {
    return this.request(`/runs/${runId}/cancel`, { method: 'POST' })
  }

  // Leaderboard
  async getLeaderboard(type: string = 'overall') {
    return this.request(`/leaderboard?type=${type}`)
  }

  // Comparison
  async compareModels(modelIds: string[], metrics?: string[]) {
    const params = new URLSearchParams()
    modelIds.forEach(id => params.append('model_ids', id))
    metrics?.forEach(m => params.append('metrics', m))
    return this.request(`/comparison?${params.toString()}`)
  }

  // System Status
  async getSystemStatus() {
    return this.request('/status')
  }

  // WebSocket for real-time updates
  connectWebSocket(runId: string, onMessage: (data: unknown) => void, onError?: (error: Event) => void) {
    const wsUrl = this.baseUrl.replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsUrl}/ws/runs/${runId}`)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch {
        onMessage(event.data)
      }
    }

    ws.onerror = (error) => {
      onError?.(error)
    }

    return ws
  }
}

export const api = new OpenCodeApi()
export default OpenCodeApi
