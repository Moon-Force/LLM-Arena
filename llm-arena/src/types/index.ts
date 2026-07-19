export interface Model {
  id: string
  name: string
  provider: string
  version: string
  description: string
  icon?: string
  color: string
  // Configuration fields
  apiKey?: string
  baseUrl?: string
  temperature?: number
  maxTokens?: number
  enabled: boolean
  custom?: boolean  // User-defined model
}

export interface ModelProvider {
  id: string
  name: string
  icon?: string
  requiresApiKey: boolean
  supportsBaseUrl: boolean
  defaultBaseUrl?: string
  models: string[]  // Available model versions
}

/** Evaluation track — partitions task pool only; same tools within a track */
export type EvalTrack =
  | 'algorithm'
  | 'bugfix'
  | 'feature'
  | 'frontend'
  | 'tooluse'
  | 'safety'
  | 'all'

export interface TrackInfo {
  id: string
  order: number
  enabled: boolean
  beta?: boolean
  name: { zh?: string; en?: string } | string
  description?: { zh?: string; en?: string } | string
  task_count?: number
  default_tools_policy?: string
  metrics?: string[]
}

export interface Task {
  id: string
  name: string
  description: string
  language: 'python' | 'typescript' | 'html' | string
  type: 'bugfix' | 'feature' | 'algorithm' | string
  difficulty: 'easy' | 'medium' | 'hard'
  testCases: number
  track?: EvalTrack | string
  custom?: boolean
  expectedFiles?: string[]
}

/** Payload for POST /api/v1/tasks */
export interface TaskCreatePayload {
  id: string
  name: string
  description: string
  language: string
  type: string
  difficulty: 'easy' | 'medium' | 'hard'
  track: string
  expected_files?: string[]
  files: Record<string, string>
  overwrite?: boolean
  force?: boolean
}

export interface AgentStepLog {
  step: number
  thought: string
  observation: string
  tool_calls: Array<{ name?: string; arguments?: unknown }>
  tokens: number
  duration_ms: number
  /** Progressive live stream: how many tools finished in this turn */
  tools_completed?: number
}

/**
 * OpenCode-style session message (anomalyco/opencode Session.Message).
 * Linear dialogue: user / assistant / system, assistant has typed content parts.
 */
export type OpenCodeMessageType =
  | 'user'
  | 'assistant'
  | 'system'
  | 'synthetic'
  | 'shell'

export type OpenCodePartType = 'text' | 'reasoning' | 'tool'

export interface OpenCodeToolState {
  status: 'pending' | 'running' | 'completed' | 'error'
  input?: unknown
  output?: string
  error?: string
}

export interface OpenCodeContentPart {
  type: OpenCodePartType
  id?: string
  text?: string
  name?: string
  /** Official BasicTool title, e.g. "Called write_file" */
  title?: string
  /** Official subtitle: path / query / url */
  subtitle?: string
  state?: OpenCodeToolState
}

export interface OpenCodeMessage {
  id: string
  type: OpenCodeMessageType
  role?: string
  text?: string
  agent?: string
  model?: string
  step?: number
  tokens?: number
  input_tokens?: number
  output_tokens?: number
  duration_ms?: number
  content?: OpenCodeContentPart[]
}

export interface ArenaRun {
  id: string
  modelId: string
  taskId: string
  track?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startedAt: string
  completedAt?: string
  duration?: number
  tokensUsed?: number
  /** Prompt / input tokens (sum over assistant turns) */
  inputTokens?: number
  /** Completion / output tokens (sum over assistant turns) */
  outputTokens?: number
  cost?: number
  testResults?: TestResult
  codeDiff?: string
  toolCalls?: ToolCall[]
  error?: string
  workspacePath?: string
  agentSteps?: AgentStepLog[]
  /** OpenCode dialogue timeline (preferred for UI) */
  agentMessages?: OpenCodeMessage[]
  agentLog?: string
  /** Loaded client-side for HTML preview (legacy srcdoc; may lack external CSS) */
  previewHtml?: string
  /** Accurate preview: real HTTP URL under API /preview/ (CSS/JS relative paths work) */
  previewUrl?: string
}

export interface TestResult {
  total: number
  passed: number
  failed: number
  hiddenPassed: number
  hiddenTotal: number
  coverage?: number
}

export interface ToolCall {
  tool: string
  timestamp: string
  duration: number
  success: boolean
}

export interface LeaderboardEntry {
  modelId: string
  modelName: string
  modelProvider: string
  modelColor: string
  runs: number
  completedRuns: number
  passRate: number
  hiddenPassRate: number
  avgTokens: number
  avgCost: number
  avgDuration: number
  stability: number
  codeQuality: number
  safetyScore: number
  overallScore: number
}

export type LeaderboardType = 'overall' | 'accuracy' | 'value'
