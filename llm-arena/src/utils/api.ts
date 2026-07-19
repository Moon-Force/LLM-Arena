// OpenCode API client
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

/** Official OpenCode tool catalog from GET /api/v1/opencode/tools */
export interface OpencodeToolInfo {
  id: string
  name: string
  category: string
  description: string
  default: 'allow' | 'deny' | 'ask' | string
  permission_key?: string
  requires_env?: string[]
  experimental?: boolean
  arena_note?: string
}

export interface OpencodeToolsPayload {
  engine: string
  docs: string
  tools: OpencodeToolInfo[]
  permission: Record<string, string>
  enabled_count: number
  denied_count: number
  enabled_ids: string[]
  denied_ids: string[]
  note: string
}

export interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  ext?: string
  preview?: boolean
  text?: boolean
  children?: FileTreeNode[]
}

class OpenCodeApi {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`
    // Avoid infinite "Starting…" when the API is hung / unreachable
    const timeoutMs = (options as { timeoutMs?: number }).timeoutMs ?? 30_000
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(url, {
        ...options,
        signal: options.signal ?? controller.signal,
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
          // ignore
        }
        throw new Error(detail)
      }

      return response.json()
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error(
          `API timeout (${timeoutMs / 1000}s): ${url} — is the backend running on port 8000?`,
        )
      }
      throw err
    } finally {
      clearTimeout(timer)
    }
  }

  async getModels() {
    return this.request('/models')
  }

  async getTracks() {
    return this.request<{
      tracks: Array<{
        id: string
        order: number
        enabled: boolean
        beta?: boolean
        name: { zh?: string; en?: string } | string
        description?: { zh?: string; en?: string } | string
        task_count?: number
        default_tools_policy?: string
        metrics?: string[]
      }>
      note?: string
    }>('/tracks')
  }

  async getTasks(params?: { track?: string; language?: string; difficulty?: string }) {
    const q = new URLSearchParams()
    if (params?.track) q.set('track', params.track)
    if (params?.language) q.set('language', params.language)
    if (params?.difficulty) q.set('difficulty', params.difficulty)
    const suffix = q.toString() ? `?${q}` : ''
    return this.request(`/tasks${suffix}`)
  }

  async getConstraints() {
    return this.request<{
      fingerprint: string
      constraints: Record<string, unknown>
      variable_allowed: string[]
      variable_forbidden: string[]
      note: string
      opencode?: OpencodeToolsPayload
    }>('/constraints')
  }

  async getOpencodeTools() {
    return this.request<OpencodeToolsPayload>('/opencode/tools')
  }

  /** .env → frontend */
  async getSecrets() {
    return this.request<{
      env_path: string
      exists: boolean
      providers: Record<string, {
        api_key: string
        apiKey: string
        base_url: string
        baseUrl: string
        has_key: boolean
        env_key: string
      }>
      models: Record<string, {
        provider: string
        api_key: string
        base_url: string
      }>
    }>('/secrets')
  }

  /** frontend → .env */
  async putSecrets(updates: Array<{
    provider: string
    api_key?: string
    apiKey?: string
    base_url?: string
    baseUrl?: string
  }>) {
    return this.request<{
      ok: boolean
      env_path: string
      updated_keys: string[]
      providers: Record<string, unknown>
    }>('/secrets', {
      method: 'PUT',
      body: JSON.stringify({ updates }),
    })
  }

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
        max_steps: options?.maxSteps,
        timeout: options?.timeout,
        api_key: options?.apiKey,
        provider: options?.provider,
        version: options?.version,
        base_url: options?.baseUrl,
      }),
    })
  }

  async startArena(payload: {
    taskId: string
    track?: string
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
        track: payload.track,
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

  async listWorkspaces() {
    return this.request<{
      workspaces: Array<{
        id: string
        batch_id: string
        folder: string
        model_id: string
        run_token: string
        root: string
        src: string
        mtime: number
      }>
      runs: Array<Record<string, unknown>>
    }>('/workspaces')
  }

  async deleteWorkspace(workspaceId: string) {
    const id = workspaceId.split('/').map(encodeURIComponent).join('/')
    return this.request<{ ok: boolean; deleted: string }>(`/workspaces/${id}`, {
      method: 'DELETE',
    })
  }

  async deleteWorkspaces(ids: string[]) {
    return this.request<{
      ok: boolean
      deleted: string[]
      errors: Array<{ id: string; error: string }>
    }>('/workspaces/delete', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    })
  }

  async listWorkspaceFiles(workspaceId: string) {
    return this.request<{
      root: string
      files: FileTreeNode[]
      html_entrypoints: string[]
      workspace_id?: string
      model_id?: string
    }>(`/workspaces/${workspaceId.split('/').map(encodeURIComponent).join('/')}/files`)
  }

  async readWorkspaceFile(workspaceId: string, path: string) {
    const q = new URLSearchParams({ path })
    const id = workspaceId.split('/').map(encodeURIComponent).join('/')
    return this.request<{
      path: string
      size: number
      mime: string
      content: string | null
      preview?: boolean
      binary?: boolean
      truncated?: boolean
    }>(`/workspaces/${id}/files/content?${q}`)
  }

  /**
   * Real static preview base (ends with /preview/).
   * Prefer iframe `src` over `srcdoc` so relative CSS/JS load correctly.
   */
  workspacePreviewUrl(workspaceId: string, entryPath = 'index.html'): string {
    const id = workspaceId.split('/').filter(Boolean).map(encodeURIComponent).join('/')
    const entry = entryPath.replace(/^\//, '')
    // this.baseUrl is like http://localhost:8000/api/v1
    return `${this.baseUrl}/workspaces/${id}/preview/${entry}`
  }

  runPreviewUrl(runId: string, entryPath = 'index.html'): string {
    const entry = entryPath.replace(/^\//, '')
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/preview/${entry}`
  }

  async getRun(runId: string) {
    return this.request(`/runs/${runId}`)
  }

  async cancelRun(runId: string) {
    return this.request(`/runs/${runId}/cancel`, { method: 'POST' })
  }

  async getLeaderboard(type: string = 'overall', track: string = 'all') {
    const q = new URLSearchParams({ type, track })
    return this.request(`/leaderboard?${q}`)
  }

  async compareModels(modelIds: string[], metrics?: string[]) {
    const params = new URLSearchParams()
    modelIds.forEach(id => params.append('model_ids', id))
    metrics?.forEach(m => params.append('metrics', m))
    return this.request(`/comparison?${params.toString()}`)
  }

  async getSystemStatus() {
    return this.request('/status')
  }

  /**
   * Live OpenCode run stream.
   * Uses VITE_WS_URL (default ws://localhost:8000/ws) — not under /api/v1.
   */
  connectWebSocket(
    runId: string,
    onMessage: (data: unknown) => void,
    onError?: (error: Event) => void,
  ) {
    const envWs = (import.meta.env.VITE_WS_URL as string | undefined)?.replace(/\/$/, '')
    const wsBase =
      envWs ||
      this.baseUrl
        .replace(/^http/, 'ws')
        .replace(/\/api\/v1\/?$/, '')
        .replace(/\/$/, '') + '/ws'
    // env is typically ws://host:8000/ws → /ws/runs/{id}
    const url = `${wsBase}/runs/${runId}`
    const ws = new WebSocket(url)
    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data))
      } catch {
        onMessage(event.data)
      }
    }
    ws.onerror = (error) => onError?.(error)
    return ws
  }
}

export const api = new OpenCodeApi()
export default OpenCodeApi
