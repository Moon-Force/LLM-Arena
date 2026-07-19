<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type FileTreeNode } from '@/utils/api'
import { useArenaStore } from '@/stores/arena'
import FileTree from '@/components/FileTree.vue'

const { t } = useI18n()
const store = useArenaStore()

interface WorkspaceItem {
  id: string
  batch_id: string
  folder: string
  model_id: string
  run_token: string
  root: string
  src: string
  mtime: number
}

interface PanelState {
  id: string
  modelId: string
  files: FileTreeNode[]
  htmlEntrypoints: string[]
  activePath: string | null
  content: string
  mode: 'code' | 'preview'
  loading: boolean
}

const workspaces = ref<WorkspaceItem[]>([])
const loading = ref(false)
const deleting = ref(false)
const error = ref<string | null>(null)
const selectedIds = ref<string[]>([])
const panels = ref<PanelState[]>([])

const batches = computed(() => {
  const map = new Map<string, WorkspaceItem[]>()
  for (const w of workspaces.value) {
    const list = map.get(w.batch_id) || []
    list.push(w)
    map.set(w.batch_id, list)
  }
  return [...map.entries()]
    .map(([batch, items]) => ({
      batch,
      items: items.sort((a, b) => b.mtime - a.mtime),
      mtime: Math.max(...items.map(i => i.mtime)),
    }))
    .sort((a, b) => b.mtime - a.mtime)
})

function modelColor(modelId: string): string {
  return store.getModelById(modelId)?.color || '#64748b'
}

function modelName(modelId: string): string {
  return store.getModelById(modelId)?.name || modelId
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

function findFirstFile(nodes: FileTreeNode[]): string | null {
  for (const n of nodes) {
    if (n.type === 'file') return n.path
    if (n.children?.length) {
      const f = findFirstFile(n.children)
      if (f) return f
    }
  }
  return null
}

function isStubHtml(html: string): boolean {
  const h = html.toLowerCase()
  if (html.length < 700) return true
  return (
    h.includes('scaffold only') ||
    h.includes('implement the pricing') ||
    h.includes('todo: implement') ||
    h.includes('a11y broken') ||
    h.includes('navbar bug') ||
    (h.includes('placeholder') && !h.includes('cta-primary') && !h.includes('todo-list'))
  )
}

async function loadList() {
  loading.value = true
  error.value = null
  try {
    const data = await api.listWorkspaces()
    workspaces.value = data.workspaces || []
    if (selectedIds.value.length === 0 && batches.value.length > 0) {
      selectedIds.value = batches.value[0].items.slice(0, 3).map(i => i.id)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load workspaces'
  } finally {
    loading.value = false
  }
}

function toggleSelect(id: string) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter(x => x !== id)
  } else if (selectedIds.value.length < 4) {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function selectBatch(batch: string) {
  const items = batches.value.find(b => b.batch === batch)?.items || []
  selectedIds.value = items.slice(0, 4).map(i => i.id)
}

async function deleteOne(id: string, ev?: Event) {
  ev?.stopPropagation()
  if (!confirm(t('outputs.confirmDelete'))) return
  deleting.value = true
  error.value = null
  try {
    await api.deleteWorkspace(id)
    selectedIds.value = selectedIds.value.filter(x => x !== id)
    await loadList()
    if (selectedIds.value.length) await loadPanels()
    else panels.value = []
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('outputs.deleteFailed')
  } finally {
    deleting.value = false
  }
}

async function deleteSelected() {
  if (!selectedIds.value.length) return
  if (!confirm(t('outputs.confirmDeleteSelected', { n: selectedIds.value.length }))) return
  deleting.value = true
  error.value = null
  try {
    const res = await api.deleteWorkspaces([...selectedIds.value])
    if (res.errors?.length) {
      error.value = res.errors.map(e => `${e.id}: ${e.error}`).join('; ')
    }
    selectedIds.value = []
    panels.value = []
    await loadList()
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('outputs.deleteFailed')
  } finally {
    deleting.value = false
  }
}

async function deleteBatch(batch: string, ev?: Event) {
  ev?.stopPropagation()
  const items = batches.value.find(b => b.batch === batch)?.items || []
  if (!items.length) return
  if (!confirm(t('outputs.confirmDeleteBatch'))) return
  deleting.value = true
  error.value = null
  try {
    const ids = items.map(i => i.id)
    const res = await api.deleteWorkspaces(ids)
    if (res.errors?.length) {
      error.value = res.errors.map(e => `${e.id}: ${e.error}`).join('; ')
    }
    selectedIds.value = selectedIds.value.filter(id => !ids.includes(id))
    if (!selectedIds.value.length) panels.value = []
    await loadList()
    if (selectedIds.value.length) await loadPanels()
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('outputs.deleteFailed')
  } finally {
    deleting.value = false
  }
}

async function loadFile(panel: PanelState, path: string) {
  panel.loading = true
  panel.activePath = path
  try {
    const data = await api.readWorkspaceFile(panel.id, path)
    panel.content = data.content ?? '(binary file)'
    panel.mode = data.preview || /\.html?$/i.test(path) ? 'preview' : 'code'
  } catch (e) {
    panel.content = e instanceof Error ? e.message : 'Failed to read file'
    panel.mode = 'code'
  } finally {
    panel.loading = false
  }
}

async function loadPanels() {
  panels.value = selectedIds.value.map(id => {
    const meta = workspaces.value.find(w => w.id === id)
    return {
      id,
      modelId: meta?.model_id || id,
      files: [],
      htmlEntrypoints: [],
      activePath: null,
      content: '',
      mode: 'code' as const,
      loading: true,
    }
  })

  await Promise.all(
    panels.value.map(async (panel) => {
      try {
        const data = await api.listWorkspaceFiles(panel.id)
        panel.files = data.files || []
        panel.htmlEntrypoints = data.html_entrypoints || []
        const html =
          panel.htmlEntrypoints.find(p => /index\.html?$/i.test(p)) ||
          panel.htmlEntrypoints[0]
        if (html) {
          await loadFile(panel, html)
        } else {
          const first = findFirstFile(panel.files)
          if (first) await loadFile(panel, first)
        }
      } catch (e) {
        panel.content = e instanceof Error ? e.message : 'Load failed'
      } finally {
        panel.loading = false
      }
    }),
  )
}

watch(selectedIds, () => {
  void loadPanels()
})

onMounted(async () => {
  await store.fetchModels()
  await loadList()
  if (selectedIds.value.length) await loadPanels()
})
</script>

<template>
  <div class="min-h-screen py-16 md:py-20 px-5 md:px-8">
    <div class="max-w-[1480px] mx-auto">
      <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
        <div>
          <div class="eyebrow mb-3">Artifacts</div>
          <h1 class="display-title text-4xl md:text-5xl mb-3">
            <span class="gradient-text">{{ t('outputs.title') }}</span>
          </h1>
          <p class="text-[#9a9488] text-lg max-w-2xl leading-relaxed">
            {{ t('outputs.subtitle') }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="px-4 py-2 text-sm rounded-xl border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 disabled:opacity-40"
            :disabled="deleting || !selectedIds.length"
            @click="deleteSelected"
          >
            {{ deleting ? t('outputs.deleting') : t('outputs.deleteSelected') }}
            <span v-if="selectedIds.length"> ({{ selectedIds.length }})</span>
          </button>
          <button
            type="button"
            class="btn-primary px-4 py-2 text-sm"
            :disabled="loading || deleting"
            @click="loadList().then(() => loadPanels())"
          >
            {{ t('outputs.refresh') }}
          </button>
        </div>
      </div>

      <div v-if="error" class="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
        {{ error }}
      </div>

      <div class="grid lg:grid-cols-4 gap-6">
        <div class="lg:col-span-1">
          <div class="glass-card p-4">
            <h2 class="text-sm font-semibold text-kimi-muted mb-3">{{ t('outputs.batches') }}</h2>
            <div v-if="loading && !workspaces.length" class="text-sm text-kimi-muted py-6 text-center">
              Loading…
            </div>
            <div v-else-if="!batches.length" class="text-sm text-kimi-muted py-6 text-center">
              {{ t('outputs.empty') }}
            </div>
            <div v-else class="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
              <div
                v-for="b in batches"
                :key="b.batch"
                class="border border-kimi-border/50 rounded-xl p-3"
              >
                <div class="flex items-center justify-between mb-2 gap-2">
                  <span class="text-xs font-mono text-kimi-muted truncate" :title="b.batch">{{ b.batch }}</span>
                  <div class="flex items-center gap-2 flex-shrink-0">
                    <button
                      type="button"
                      class="text-xs text-blue-400 hover:underline"
                      @click="selectBatch(b.batch)"
                    >
                      {{ t('outputs.selectAll') }}
                    </button>
                    <button
                      type="button"
                      class="text-xs text-rose-400 hover:underline disabled:opacity-40"
                      :disabled="deleting"
                      @click="deleteBatch(b.batch, $event)"
                    >
                      {{ t('outputs.deleteBatch') }}
                    </button>
                  </div>
                </div>
                <p class="text-[10px] text-kimi-muted mb-2">{{ formatTime(b.mtime) }}</p>
                <div class="space-y-1.5">
                  <div
                    v-for="w in b.items"
                    :key="w.id"
                    class="w-full flex items-center gap-2 p-2 rounded-lg text-sm border transition-colors"
                    :class="selectedIds.includes(w.id)
                      ? 'border-blue-500/40 bg-blue-500/10'
                      : 'border-transparent hover:bg-kimi-surface'"
                  >
                    <button
                      type="button"
                      class="flex items-center gap-2 min-w-0 flex-1 text-left"
                      @click="toggleSelect(w.id)"
                    >
                      <div
                        class="w-6 h-6 rounded-md flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"
                        :style="{ backgroundColor: modelColor(w.model_id) }"
                      >
                        {{ modelName(w.model_id).charAt(0) }}
                      </div>
                      <div class="min-w-0">
                        <div class="truncate font-medium text-kimi-text">{{ modelName(w.model_id) }}</div>
                        <div class="truncate text-[10px] text-kimi-muted font-mono">{{ w.run_token }}</div>
                      </div>
                    </button>
                    <button
                      type="button"
                      class="text-[11px] text-rose-400 hover:text-rose-300 px-1.5 py-0.5 rounded hover:bg-rose-500/10 flex-shrink-0 disabled:opacity-40"
                      :disabled="deleting"
                      :title="t('outputs.delete')"
                      @click="deleteOne(w.id, $event)"
                    >
                      {{ t('outputs.delete') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <p class="text-[11px] text-kimi-muted mt-3">{{ t('outputs.selectHint') }}</p>
          </div>
        </div>

        <div class="lg:col-span-3">
          <div v-if="!panels.length" class="glass-card p-12 text-center text-kimi-muted">
            {{ t('outputs.pickAgents') }}
          </div>
          <div
            v-else
            class="grid gap-4"
            :class="panels.length === 1 ? 'grid-cols-1' : panels.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 xl:grid-cols-3'"
          >
            <div
              v-for="panel in panels"
              :key="panel.id"
              class="glass-card flex flex-col min-h-[520px] overflow-hidden"
            >
              <div class="flex items-center gap-2 px-4 py-3 border-b border-kimi-border/40">
                <div
                  class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold"
                  :style="{ backgroundColor: modelColor(panel.modelId) }"
                >
                  {{ modelName(panel.modelId).charAt(0) }}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="font-semibold text-sm text-kimi-text truncate">{{ modelName(panel.modelId) }}</div>
                  <div class="text-[10px] text-kimi-muted font-mono truncate">{{ panel.id }}</div>
                </div>
                <div class="flex gap-1 items-center">
                  <button
                    type="button"
                    class="px-2 py-1 rounded text-xs"
                    :class="panel.mode === 'code' ? 'bg-blue-500/20 text-blue-300' : 'text-kimi-muted'"
                    @click="panel.mode = 'code'"
                  >
                    Code
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 rounded text-xs disabled:opacity-40"
                    :class="panel.mode === 'preview' ? 'bg-emerald-500/20 text-emerald-300' : 'text-kimi-muted'"
                    :disabled="!panel.activePath || !/\.html?$/i.test(panel.activePath || '')"
                    @click="panel.mode = 'preview'"
                  >
                    Page
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 rounded text-xs text-rose-400 hover:bg-rose-500/15 disabled:opacity-40"
                    :disabled="deleting"
                    @click="deleteOne(panel.id)"
                  >
                    {{ t('outputs.delete') }}
                  </button>
                </div>
              </div>

              <div class="flex flex-1 min-h-0">
                <div class="w-36 flex-shrink-0 border-r border-kimi-border/40 p-2 overflow-y-auto text-xs">
                  <FileTree
                    :nodes="panel.files"
                    :active="panel.activePath"
                    @select="(p) => loadFile(panel, p)"
                  />
                </div>
                <div class="flex-1 min-w-0 relative bg-kimi-surface/30">
                  <div
                    v-if="panel.loading"
                    class="absolute inset-0 flex items-center justify-center text-kimi-muted text-sm"
                  >
                    …
                  </div>
                  <div
                    v-else-if="panel.mode === 'preview' && panel.content"
                    class="flex flex-col h-full min-h-[420px]"
                  >
                    <div
                      v-if="isStubHtml(panel.content)"
                      class="px-3 py-2 text-xs bg-amber-500/15 text-amber-300 border-b border-amber-500/20"
                    >
                      仍是任务脚手架/占位页，agent 可能未真正写完 HTML。请重新在 Arena 跑该任务（已增强 HTML 写入逻辑）。
                    </div>
                    <iframe
                      class="w-full flex-1 min-h-[380px] bg-white"
                      sandbox="allow-scripts allow-forms"
                      :srcdoc="panel.content"
                      title="Agent page preview"
                    />
                  </div>
                  <pre
                    v-else
                    class="p-3 text-[11px] leading-relaxed overflow-auto h-full min-h-[420px] text-kimi-text font-mono whitespace-pre-wrap"
                  >{{ panel.content || t('outputs.noFile') }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
