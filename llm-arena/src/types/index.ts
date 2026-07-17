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

export interface Task {
  id: string
  name: string
  description: string
  language: 'python' | 'typescript'
  type: 'bugfix' | 'feature'
  difficulty: 'easy' | 'medium' | 'hard'
  testCases: number
}

export interface ArenaRun {
  id: string
  modelId: string
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  startedAt: string
  completedAt?: string
  duration?: number
  tokensUsed?: number
  cost?: number
  testResults?: TestResult
  codeDiff?: string
  toolCalls?: ToolCall[]
  error?: string
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
