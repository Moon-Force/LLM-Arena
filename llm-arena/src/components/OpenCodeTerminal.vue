<script setup lang="ts">
/**
 * OpenCode-style session transcript (closer to anomalyco/opencode session-ui):
 * - SessionTurn timeline (user → assistant parts)
 * - BasicTool collapsible rows: "Called {tool}" + path subtitle + details
 * - Thinking shimmer while running
 * @see packages/session-ui/src/components/session-turn.tsx
 * @see packages/session-ui/src/components/basic-tool.tsx
 */
import { computed, ref, watch, nextTick } from 'vue'
import type { AgentStepLog, OpenCodeMessage, OpenCodeContentPart } from '@/types'

const props = defineProps<{
  modelName: string
  modelColor?: string
  status?: string
  steps?: AgentStepLog[]
  messages?: OpenCodeMessage[]
  agentLog?: string
  error?: string
  tokens?: number
  inputTokens?: number
  outputTokens?: number
  duration?: number
}>()

const scroller = ref<HTMLElement | null>(null)
const showRaw = ref(false)
/** tool part open state — completed tools default collapsed (official) */
const toolOpen = ref<Record<string, boolean>>({})
const textOpen = ref<Record<string, boolean>>({})

const dialogue = computed<OpenCodeMessage[]>(() => {
  if (props.messages && props.messages.length > 0) return props.messages
  return stepsToMessages(props.steps || [], props.modelName, props.error)
})

const turns = computed(() => {
  // Group like SessionTurn: each user starts a turn; assistant msgs follow
  const list = dialogue.value
  const out: { user?: OpenCodeMessage; assistants: OpenCodeMessage[] }[] = []
  let cur: { user?: OpenCodeMessage; assistants: OpenCodeMessage[] } = { assistants: [] }
  for (const m of list) {
    if (m.type === 'user') {
      if (cur.user || cur.assistants.length) out.push(cur)
      cur = { user: m, assistants: [] }
    } else if (m.type === 'assistant') {
      cur.assistants.push(m)
    } else if (m.type === 'system') {
      if (cur.user || cur.assistants.length) out.push(cur)
      cur = { assistants: [] }
      out.push({ assistants: [], user: m as OpenCodeMessage })
    }
  }
  if (cur.user || cur.assistants.length) out.push(cur)
  // If only assistants (no user yet from API), still show them
  if (out.length === 0 && list.length) {
    out.push({ assistants: list.filter(m => m.type === 'assistant') })
  }
  return out
})

const hasDialogue = computed(() => dialogue.value.length > 0)
const assistantTurns = computed(() => dialogue.value.filter(m => m.type === 'assistant').length)
const toolCount = computed(() =>
  dialogue.value.reduce((n, m) => n + (m.content?.filter(p => p.type === 'tool').length || 0), 0),
)

const isRunning = computed(() => props.status === 'running' || props.status === 'pending')
/** Official: Thinking only while waiting for the next assistant turn (not forever after content). */
const showThinking = computed(() => {
  if (!isRunning.value) return false
  const assistants = dialogue.value.filter(m => m.type === 'assistant')
  if (assistants.length === 0) return true
  const last = assistants[assistants.length - 1]
  const hasRunningTool = last.content?.some(
    p => p.type === 'tool' && (p.state?.status === 'pending' || p.state?.status === 'running'),
  )
  // Between turns: last assistant finished (has text or completed tools) → still show thinking
  // while status is running (model may be generating next step)
  // While status is running, keep a soft working indicator (next turn may be generating)
  return true
})

const thinkingLabel = computed(() => {
  if (!isRunning.value) return ''
  if (assistantTurns.value === 0) {
    return 'Thinking — waiting for first model response…'
  }
  return `Thinking — turn ${assistantTurns.value + 1}…`
})

/** Track newest turn for step-enter animation */
const latestStep = computed(() => {
  const steps = props.steps || []
  if (!steps.length) return 0
  return Math.max(...steps.map(s => s.step || 0))
})

watch(
  () => [
    props.messages?.length,
    props.steps?.length,
    props.status,
    dialogue.value.length,
    // Re-scroll on mid-step progress (tool completions / thought growth)
    props.steps?.at(-1)?.tools_completed,
    props.steps?.at(-1)?.thought?.length,
    props.agentLog?.length,
  ],
  async () => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  },
)

function stepsToMessages(steps: AgentStepLog[], modelName: string, error?: string): OpenCodeMessage[] {
  const out: OpenCodeMessage[] = []
  let i = 0
  const mid = () => `local_${++i}`
  for (const s of steps) {
    const content: OpenCodeContentPart[] = []
    const clean = stripFences(s.thought || '', !!(s.tool_calls?.length))
    if (clean) content.push({ type: 'text', id: `t_${s.step}`, text: clean })
    for (const [ti, tc] of (s.tool_calls || []).entries()) {
      const name = tc.name || 'tool'
      const args = (tc.arguments || {}) as Record<string, unknown>
      content.push({
        type: 'tool',
        id: `tool_${s.step}_${ti}`,
        name,
        title: `Called ${name}`,
        subtitle: toolSubtitle(name, args),
        state: {
          status: 'completed',
          input: args,
          output: (s.tool_calls?.length || 0) === 1 ? s.observation : undefined,
        },
      })
    }
    if (s.observation && (s.tool_calls?.length || 0) > 1) {
      const last = content.filter(c => c.type === 'tool').at(-1)
      if (last?.state) last.state.output = s.observation
    }
    if (s.observation && !(s.tool_calls?.length)) {
      content.push({
        type: 'tool',
        id: `obs_${s.step}`,
        name: 'observation',
        title: 'Called observation',
        state: { status: 'completed', input: {}, output: s.observation },
      })
    }
    if (content.length) {
      out.push({
        id: mid(),
        type: 'assistant',
        agent: 'build',
        model: modelName,
        step: s.step,
        tokens: s.tokens,
        duration_ms: s.duration_ms,
        content,
      })
    }
  }
  if (error) out.push({ id: mid(), type: 'system', text: error })
  return out
}

function stripFences(text: string, hadTools: boolean): string {
  if (!text) return ''
  if (!hadTools) return text.trim()
  return text
    .replace(/```(?:tool|html|htm|css|js|javascript|ts|typescript|python|py|json)[^\n]*\n[\s\S]*?```/gi, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function toolSubtitle(_name: string, args: Record<string, unknown>): string {
  for (const key of ['path', 'filePath', 'file', 'query', 'url', 'pattern', 'description', 'command']) {
    const v = args[key]
    if (typeof v === 'string' && v.trim()) {
      return v.length > 72 ? v.slice(0, 69) + '…' : v
    }
  }
  return ''
}

function fmtJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function isToolOpen(id: string, status?: string): boolean {
  if (toolOpen.value[id] !== undefined) return toolOpen.value[id]
  // Official: pending/running force "open" appearance (title only, no details while pending)
  if (status === 'pending' || status === 'running') return false
  // completed: default collapsed
  return false
}

function toggleTool(id: string) {
  toolOpen.value[id] = !isToolOpen(id)
}

function isTextOpen(id: string, len: number): boolean {
  if (textOpen.value[id] !== undefined) return textOpen.value[id]
  return len <= 1200
}

function toggleText(id: string, len: number) {
  textOpen.value[id] = !isTextOpen(id, len)
}

function argChips(input: unknown): string[] {
  if (!input || typeof input !== 'object') return []
  const skip = new Set(['path', 'filePath', 'file', 'query', 'url', 'pattern', 'name', 'description', 'content'])
  return Object.entries(input as Record<string, unknown>)
    .filter(([k]) => !skip.has(k))
    .flatMap(([k, v]) => {
      if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return [`${k}=${v}`]
      return []
    })
    .slice(0, 3)
}
</script>

<template>
  <div
    class="oc-session flex flex-col h-full min-h-[420px] rounded-b-xl overflow-hidden border-t border-white/[0.06]"
    data-component="session-turn"
  >
    <!-- session chrome (minimal, like desktop app header strip) -->
    <div class="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06] bg-[#0e1016] text-[11px] shrink-0">
      <span
        class="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold text-white"
        :style="{ backgroundColor: modelColor || '#6366f1' }"
      >
        {{ modelName?.charAt(0) || 'O' }}
      </span>
      <div class="min-w-0 flex-1">
        <div class="text-slate-200 text-xs font-medium truncate">{{ modelName }}</div>
        <div class="text-slate-500 text-[10px] font-mono truncate">
          agent build
          <span v-if="inputTokens != null || outputTokens != null" class="text-slate-400">
            ·
            <span class="text-sky-400/90">in {{ (inputTokens ?? 0).toLocaleString() }}</span>
            <span class="text-slate-600">/</span>
            <span class="text-amber-400/90">out {{ (outputTokens ?? 0).toLocaleString() }}</span>
          </span>
          <span v-else-if="tokens != null"> · {{ tokens.toLocaleString() }} tok</span>
          <span v-if="tokens != null && (inputTokens != null || outputTokens != null)" class="text-slate-600">
            · Σ {{ tokens.toLocaleString() }}
          </span>
          <span> · {{ assistantTurns }} turn<span v-if="assistantTurns !== 1">s</span></span>
          <span v-if="toolCount"> · {{ toolCount }} tool<span v-if="toolCount !== 1">s</span></span>
        </div>
      </div>
      <span
        class="text-[10px] px-2 py-0.5 rounded-full font-medium"
        :class="{
          'bg-blue-500/15 text-blue-300': isRunning,
          'bg-emerald-500/15 text-emerald-300': status === 'completed' || status === 'success',
          'bg-rose-500/15 text-rose-300': status === 'failed',
          'bg-white/5 text-slate-400': !isRunning && status !== 'completed' && status !== 'success' && status !== 'failed',
        }"
      >
        {{ status || 'idle' }}
      </span>
      <button type="button" class="text-slate-500 hover:text-slate-300 text-[11px]" @click="showRaw = !showRaw">
        {{ showRaw ? 'session' : 'raw' }}
      </button>
    </div>

    <pre
      v-if="showRaw"
      ref="scroller"
      class="flex-1 overflow-auto p-3 text-[11px] font-mono text-slate-300 whitespace-pre-wrap leading-relaxed bg-[#0a0b10]"
    >{{ agentLog || error || '(empty transcript)' }}</pre>

    <!-- timeline (session-turn-content) -->
    <div
      v-else
      ref="scroller"
      data-slot="session-turn-content"
      class="flex-1 overflow-auto px-3 py-4 space-y-6 bg-[#0a0b10]"
    >
      <div v-if="!hasDialogue && !isRunning" class="text-center text-slate-500 text-sm py-12">
        Waiting for OpenCode session…
      </div>

      <!-- turns -->
      <div
        v-for="(turn, ti) in turns"
        :key="ti"
        data-slot="session-turn-message-container"
        class="space-y-3"
      >
        <!-- USER (task) — full width card like official user message -->
        <div
          v-if="turn.user && turn.user.type === 'user'"
          class="rounded-xl border border-white/[0.08] bg-[#141722] px-3.5 py-3"
        >
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">You</span>
            <span class="text-[10px] text-slate-600">task</span>
          </div>
          <div class="text-[13px] text-slate-200 leading-relaxed whitespace-pre-wrap break-words">
            <template v-if="isTextOpen(turn.user.id, turn.user.text?.length || 0)">
              {{ turn.user.text }}
            </template>
            <template v-else>
              {{ (turn.user.text || '').slice(0, 600) }}…
            </template>
          </div>
          <button
            v-if="(turn.user.text?.length || 0) > 600"
            type="button"
            class="mt-1.5 text-[11px] text-indigo-300/80 hover:text-indigo-200"
            @click="toggleText(turn.user.id, turn.user.text?.length || 0)"
          >
            {{ isTextOpen(turn.user.id, turn.user.text?.length || 0) ? 'Show less' : 'Show more' }}
          </button>
        </div>

        <!-- system as centered notice -->
        <div
          v-else-if="turn.user && turn.user.type === 'system'"
          class="flex justify-center"
        >
          <div class="text-[11px] text-slate-500 bg-white/[0.04] border border-white/[0.06] px-3 py-1 rounded-full">
            {{ turn.user.text }}
          </div>
        </div>

        <!-- ASSISTANT content stack (session-turn-assistant-content) -->
        <div
          v-for="msg in turn.assistants"
          :key="msg.id"
          data-slot="session-turn-assistant-content"
          class="space-y-2.5 pl-0.5 oc-step-enter"
          :class="{ 'oc-step-latest': isRunning && msg.step === latestStep }"
        >
          <div class="flex items-center gap-2 text-[10px] text-slate-500">
            <span
              v-if="msg.step != null"
              class="inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[10px] font-semibold"
              :class="isRunning && msg.step === latestStep
                ? 'bg-violet-500/25 text-violet-200 ring-1 ring-violet-400/40'
                : 'bg-white/[0.06] text-slate-400'"
            >
              Step {{ msg.step }}
            </span>
            <span class="font-medium text-slate-400">OpenCode</span>
            <span class="text-slate-600">·</span>
            <span class="font-mono">{{ msg.agent || 'build' }}</span>
            <span
              v-if="msg.input_tokens != null || msg.output_tokens != null"
              class="font-mono text-slate-500"
            >
              ·
              <span class="text-sky-400/80">in {{ (msg.input_tokens ?? 0).toLocaleString() }}</span>
              /
              <span class="text-amber-400/80">out {{ (msg.output_tokens ?? 0).toLocaleString() }}</span>
            </span>
            <span v-else-if="msg.tokens" class="font-mono text-slate-600">· {{ msg.tokens }} tok</span>
            <span
              v-if="isRunning && msg.step === latestStep"
              class="text-[10px] text-violet-300/90 animate-pulse"
            >
              live
            </span>
          </div>

          <template v-for="part in msg.content || []" :key="part.id || part.type + (part.name || '')">
            <!-- TEXT -->
            <div
              v-if="part.type === 'text' && part.text?.trim()"
              class="text-[13.5px] text-slate-200 leading-[1.65] whitespace-pre-wrap break-words"
            >
              <template v-if="isTextOpen(part.id || msg.id, part.text.length)">
                {{ part.text }}
              </template>
              <template v-else>
                {{ part.text.slice(0, 1200) }}…
                <button
                  type="button"
                  class="block mt-1 text-[11px] text-indigo-300/80 hover:text-indigo-200"
                  @click="toggleText(part.id || msg.id, part.text.length)"
                >
                  Show more
                </button>
              </template>
              <button
                v-if="isTextOpen(part.id || msg.id, part.text.length) && part.text.length > 1200"
                type="button"
                class="block mt-1 text-[11px] text-indigo-300/80 hover:text-indigo-200"
                @click="toggleText(part.id || msg.id, part.text.length)"
              >
                Show less
              </button>
            </div>

            <!-- REASONING (collapsible, weak text) -->
            <details
              v-else-if="part.type === 'reasoning' && part.text?.trim()"
              class="group rounded-lg border border-white/[0.06] bg-white/[0.02]"
            >
              <summary class="cursor-pointer px-3 py-2 text-[12px] text-slate-400 hover:text-slate-300 list-none flex items-center gap-2">
                <span class="text-slate-500 group-open:rotate-90 transition-transform">▸</span>
                Reasoning
              </summary>
              <div class="px-3 pb-3 text-[12px] text-slate-400/90 whitespace-pre-wrap leading-relaxed border-t border-white/[0.04] pt-2">
                {{ part.text }}
              </div>
            </details>

            <!-- TOOL (BasicTool-like) -->
            <div
              v-else-if="part.type === 'tool'"
              class="tool-collapsible rounded-lg border border-white/[0.07] bg-[#12151e] overflow-hidden"
              data-component="tool-trigger"
            >
              <button
                type="button"
                class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/[0.03] transition-colors"
                :disabled="part.state?.status === 'pending' || part.state?.status === 'running'"
                @click="toggleTool(part.id || msg.id + (part.name || ''))"
              >
                <span
                  class="w-5 h-5 rounded flex items-center justify-center text-[11px] shrink-0"
                  :class="{
                    'bg-cyan-500/15 text-cyan-300': part.state?.status === 'completed',
                    'bg-amber-500/15 text-amber-300 animate-pulse': part.state?.status === 'pending' || part.state?.status === 'running',
                    'bg-rose-500/15 text-rose-300': part.state?.status === 'error',
                  }"
                >
                  ⚙
                </span>
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span
                      class="text-[12.5px] font-medium"
                      :class="(part.state?.status === 'pending' || part.state?.status === 'running')
                        ? 'text-slate-300 animate-pulse'
                        : 'text-slate-200'"
                    >
                      {{ part.title || `Called ${part.name}` }}
                    </span>
                    <span
                      v-if="part.subtitle && !(part.state?.status === 'pending' || part.state?.status === 'running')"
                      class="text-[11px] text-slate-500 truncate max-w-[220px] font-mono"
                      :title="part.subtitle"
                    >
                      {{ part.subtitle }}
                    </span>
                    <span
                      v-for="chip in argChips(part.state?.input)"
                      :key="chip"
                      class="text-[10px] text-slate-500 font-mono bg-white/[0.04] px-1.5 py-0.5 rounded"
                    >
                      {{ chip }}
                    </span>
                  </div>
                </div>
                <span
                  v-if="part.state?.output || (part.state?.input && Object.keys(part.state.input as object).length)"
                  class="text-slate-600 text-[10px] shrink-0"
                >
                  {{ isToolOpen(part.id || msg.id + (part.name || ''), part.state?.status) ? '▾' : '▸' }}
                </span>
              </button>

              <div
                v-if="isToolOpen(part.id || msg.id + (part.name || ''), part.state?.status)
                  && (part.state?.output || part.state?.input)"
                class="border-t border-white/[0.05] px-3 py-2 space-y-2 bg-[#0c0e14]"
              >
                <div v-if="part.state?.input && Object.keys(part.state.input as object).length">
                  <div class="text-[10px] uppercase tracking-wider text-slate-500 mb-1">input</div>
                  <pre class="text-[11px] font-mono text-slate-400 whitespace-pre-wrap break-words max-h-36 overflow-auto">{{ fmtJson(part.state.input) }}</pre>
                </div>
                <div v-if="part.state?.output">
                  <div class="text-[10px] uppercase tracking-wider text-slate-500 mb-1">output</div>
                  <pre class="text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words max-h-44 overflow-auto">{{ part.state.output }}</pre>
                </div>
                <div v-if="part.state?.error" class="text-[12px] text-rose-300">
                  {{ part.state.error }}
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Thinking row (official session-turn-thinking) -->
      <div
        v-if="showThinking"
        data-slot="session-turn-thinking"
        class="flex items-center gap-2 text-[13px] text-slate-500 min-h-5"
      >
        <span class="oc-shimmer font-medium">{{ thinkingLabel }}</span>
        <span class="inline-flex gap-0.5">
          <span class="w-1 h-1 rounded-full bg-slate-500 animate-bounce [animation-delay:0ms]" />
          <span class="w-1 h-1 rounded-full bg-slate-500 animate-bounce [animation-delay:150ms]" />
          <span class="w-1 h-1 rounded-full bg-slate-500 animate-bounce [animation-delay:300ms]" />
        </span>
      </div>

      <div
        v-if="error && hasDialogue"
        class="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-[12px] text-rose-200 whitespace-pre-wrap error-card"
      >
        {{ error }}
      </div>

      <div
        v-if="status === 'completed' || status === 'success'"
        class="text-center text-[11px] text-slate-500 pt-2 pb-1"
      >
        Session complete
      </div>
      <div
        v-else-if="status === 'failed' && !error"
        class="text-center text-[11px] text-rose-400/80 pt-2"
      >
        Session failed
      </div>
    </div>
  </div>
</template>

<style scoped>
.oc-shimmer {
  background: linear-gradient(
    90deg,
    rgb(100 116 139) 0%,
    rgb(203 213 225) 40%,
    rgb(100 116 139) 80%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: oc-shimmer 1.6s ease-in-out infinite;
}
@keyframes oc-shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
/* Progressive step reveal */
.oc-step-enter {
  animation: oc-step-in 0.35s ease-out;
}
.oc-step-latest {
  border-left: 2px solid rgb(167 139 250 / 0.45);
  padding-left: 0.5rem;
  margin-left: -0.125rem;
}
@keyframes oc-step-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
