<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useArenaStore } from '@/stores/arena'
import { api } from '@/utils/api'
import type { Task } from '@/types'

const { t, locale } = useI18n()
const store = useArenaStore()
const router = useRouter()

const mode = ref<'list' | 'create' | 'edit'>('list')
const saving = ref(false)
const loadingDetail = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const filterTrack = ref('all')

// form
const formId = ref('')
const formName = ref('')
const formDescription = ref('')
const formLanguage = ref('python')
const formType = ref('feature')
const formDifficulty = ref<'easy' | 'medium' | 'hard'>('medium')
const formTrack = ref('feature')
const starterName = ref('solution.py')
const starterCode = ref('')
const testName = ref('test_solution.py')
const testCode = ref('')
const extraFilesJson = ref('{}')
const editingBuiltin = ref(false)

const templates = [
  { id: 'py-feature', label: 'Python · Feature', language: 'python', type: 'feature', track: 'feature' },
  { id: 'py-bugfix', label: 'Python · Bugfix', language: 'python', type: 'bugfix', track: 'bugfix' },
  { id: 'py-algo', label: 'Python · Algorithm', language: 'python', type: 'algorithm', track: 'algorithm' },
  { id: 'html-ui', label: 'HTML · Frontend', language: 'html', type: 'feature', track: 'frontend' },
]

const filteredTasks = computed(() => {
  const list = store.tasks
  if (filterTrack.value === 'all') return list
  return list.filter(t => (t.track || '') === filterTrack.value)
})

const canSave = computed(() => {
  return (
    !!formId.value.trim()
    && !!formName.value.trim()
    && !!formDescription.value.trim()
    && !!starterCode.value.trim()
    && !!testCode.value.trim()
    && !saving.value
  )
})

function trackLabel(tr: { id: string; name?: { zh?: string; en?: string } | string }): string {
  const n = tr.name
  if (!n) return tr.id
  if (typeof n === 'string') return n
  return (locale.value === 'zh' ? n.zh : n.en) || n.zh || n.en || tr.id
}

function applyTemplate(templateId: string) {
  const tpl = templates.find(x => x.id === templateId)
  if (!tpl) return
  formLanguage.value = tpl.language
  formType.value = tpl.type
  formTrack.value = tpl.track

  if (tpl.id === 'html-ui') {
    starterName.value = 'index.html'
    testName.value = 'test_page.py'
    // Avoid raw <script> tags inside .vue SFC (breaks Vue compiler)
    starterCode.value = [
      '<!DOCTYPE html>',
      '<html lang="zh-CN">',
      '<head>',
      '  <meta charset="UTF-8" />',
      '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
      '  <title>Task Page</title>',
      '  <style>',
      '    body { font-family: system-ui, sans-serif; margin: 2rem; }',
      '    #app { max-width: 720px; margin: 0 auto; }',
      '    #status { color: #666; }',
      '  </style>',
      '</head>',
      '<body>',
      '  <div id="app">',
      '    <h1 id="title">Hello Arena</h1>',
      '    <button id="action-btn" type="button">Click</button>',
      '    <p id="status">idle</p>',
      '  </div>',
      '  <' + 'script>',
      "    document.getElementById('action-btn')?.addEventListener('click', () => {",
      "      document.getElementById('status').textContent = 'done';",
      '    });',
      '  </' + 'script>',
      '</body>',
      '</html>',
      '',
    ].join('\n')
    testCode.value = `from pathlib import Path


def _html() -> str:
    return Path("index.html").read_text(encoding="utf-8")


def test_has_title():
    html = _html()
    assert 'id="title"' in html


def test_has_action_button():
    html = _html()
    assert 'id="action-btn"' in html


def test_status_element():
    html = _html()
    assert 'id="status"' in html
`
  } else if (tpl.id === 'py-bugfix') {
    starterName.value = 'solution.py'
    testName.value = 'test_solution.py'
    starterCode.value = `def process(items):
    """BUG: crashes on None entries. Fix without changing normal behavior."""
    out = []
    for x in items:
        out.append(x.strip().upper())
    return out
`
    testCode.value = `from solution import process


def test_normal():
    assert process(["a", "b"]) == ["A", "B"]


def test_skips_none():
    assert process(["a", None, "b"]) == ["A", "B"]


def test_empty():
    assert process([]) == []
`
  } else if (tpl.id === 'py-algo') {
    starterName.value = 'solution.py'
    testName.value = 'test_solution.py'
    starterCode.value = `def solve(n: int) -> int:
    """Return n-th Fibonacci number (0-indexed: F0=0, F1=1)."""
    raise NotImplementedError
`
    testCode.value = `from solution import solve


def test_base():
    assert solve(0) == 0
    assert solve(1) == 1


def test_small():
    assert solve(10) == 55
`
  } else {
    starterName.value = 'solution.py'
    testName.value = 'test_solution.py'
    starterCode.value = `def add(a: int, b: int) -> int:
    """Return a + b."""
    raise NotImplementedError("implement me")
`
    testCode.value = `from solution import add


def test_add_positive():
    assert add(2, 3) == 5


def test_add_zero():
    assert add(0, 0) == 0


def test_add_negative():
    assert add(-1, 4) == 3
`
  }
  if (!formId.value) {
    formId.value = `custom-${tpl.type}-1`
  }
  if (!formName.value) {
    formName.value = formId.value
  }
  if (!formDescription.value) {
    formDescription.value = '在此描述任务目标、API 与完成标准。模型会看到这段说明 + 仓库文件。'
  }
}

function resetForm() {
  formId.value = ''
  formName.value = ''
  formDescription.value = ''
  formLanguage.value = 'python'
  formType.value = 'feature'
  formDifficulty.value = 'medium'
  formTrack.value = 'feature'
  starterName.value = 'solution.py'
  starterCode.value = ''
  testName.value = 'test_solution.py'
  testCode.value = ''
  extraFilesJson.value = '{}'
  editingBuiltin.value = false
  error.value = null
  success.value = null
}

function openCreate() {
  resetForm()
  applyTemplate('py-feature')
  mode.value = 'create'
}

async function openEdit(task: Task) {
  error.value = null
  success.value = null
  loadingDetail.value = true
  mode.value = 'edit'
  editingBuiltin.value = !task.custom
  try {
    const detail = await api.getTask(task.id, true)
    formId.value = String(detail.id || task.id)
    formName.value = String(detail.name || task.name)
    formDescription.value = String(detail.description || '')
    formLanguage.value = String(detail.language || 'python')
    formType.value = String(detail.type || 'feature')
    formDifficulty.value = (detail.difficulty as 'easy' | 'medium' | 'hard') || 'medium'
    formTrack.value = String(detail.track || 'feature')
    const files = (detail.files || {}) as Record<string, string>
    const names = Object.keys(files)
    const testFile = names.find(n => n.startsWith('test_') && n.endsWith('.py')) || names.find(n => n.endsWith('_test.py'))
    const starterFile = names.find(n => n !== testFile) || names[0]
    if (starterFile) {
      starterName.value = starterFile
      starterCode.value = files[starterFile] || ''
    }
    if (testFile) {
      testName.value = testFile
      testCode.value = files[testFile] || ''
    }
    const rest: Record<string, string> = {}
    for (const [k, v] of Object.entries(files)) {
      if (k !== starterFile && k !== testFile) rest[k] = v
    }
    extraFilesJson.value = JSON.stringify(rest, null, 2)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loadingDetail.value = false
  }
}

function buildFiles(): Record<string, string> {
  const files: Record<string, string> = {
    [starterName.value.trim()]: starterCode.value,
    [testName.value.trim()]: testCode.value,
  }
  try {
    const extra = JSON.parse(extraFilesJson.value || '{}') as Record<string, string>
    if (extra && typeof extra === 'object') {
      for (const [k, v] of Object.entries(extra)) {
        if (k && typeof v === 'string') files[k] = v
      }
    }
  } catch {
    throw new Error(t('tasks.invalidExtraJson'))
  }
  return files
}

async function saveTask() {
  error.value = null
  success.value = null
  if (!canSave.value) return
  saving.value = true
  try {
    const files = buildFiles()
    const payload = {
      id: formId.value.trim().toLowerCase(),
      name: formName.value.trim(),
      description: formDescription.value,
      language: formLanguage.value,
      type: formType.value,
      difficulty: formDifficulty.value,
      track: formTrack.value,
      expected_files: Object.keys(files),
      files,
      overwrite: mode.value === 'edit',
      force: editingBuiltin.value,
    }
    if (mode.value === 'edit') {
      await api.updateTask(payload.id, payload)
      success.value = t('tasks.updated')
    } else {
      await api.createTask(payload)
      success.value = t('tasks.created')
    }
    await store.fetchTasks(store.selectedTrack)
    await store.fetchTracks()
    mode.value = 'list'
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

async function removeTask(task: Task) {
  if (!task.custom) {
    if (!confirm(t('tasks.confirmDeleteBuiltin'))) return
  } else if (!confirm(t('tasks.confirmDelete', { id: task.id }))) {
    return
  }
  error.value = null
  try {
    await api.deleteTask(task.id, !task.custom)
    success.value = t('tasks.deleted')
    await store.fetchTasks(filterTrack.value === 'all' ? undefined : filterTrack.value)
    await store.fetchTracks()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

async function reloadFromDisk() {
  error.value = null
  try {
    const r = await api.reloadTasks()
    success.value = t('tasks.reloaded', { n: r.count })
    await store.fetchTasks(filterTrack.value === 'all' ? undefined : filterTrack.value)
    await store.fetchTracks()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

function goArena(taskId: string) {
  store.setSelectedTrack(
    store.tasks.find(t => t.id === taskId)?.track || store.selectedTrack,
  )
  router.push({ path: '/arena' })
}

watch(formLanguage, (lang) => {
  if (mode.value !== 'create') return
  if (lang === 'html' && starterName.value.endsWith('.py')) {
    // user switched language manually — offer html defaults if empty-ish
  }
})

onMounted(async () => {
  await store.fetchTracks()
  await store.fetchTasks(filterTrack.value === 'all' ? undefined : filterTrack.value)
})

watch(filterTrack, async (tr) => {
  await store.fetchTasks(tr === 'all' ? undefined : tr)
})
</script>

<template>
  <div class="min-h-screen py-16 md:py-20 px-5 md:px-8">
    <div class="max-w-[1100px] mx-auto">
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
        <div>
          <div class="eyebrow mb-3">Task lab</div>
          <h1 class="display-title text-4xl md:text-5xl mb-3">
            <span class="gradient-text">{{ t('tasks.title') }}</span>
          </h1>
          <p class="text-[#9a9488] text-lg max-w-2xl leading-relaxed">
            {{ t('tasks.subtitle') }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button type="button" class="btn-secondary !py-2 !px-4 !text-sm" @click="reloadFromDisk">
            {{ t('tasks.reload') }}
          </button>
          <button
            v-if="mode === 'list'"
            type="button"
            class="btn-primary !py-2 !px-4 !text-sm"
            @click="openCreate"
          >
            {{ t('tasks.new') }}
          </button>
          <button
            v-else
            type="button"
            class="btn-secondary !py-2 !px-4 !text-sm"
            @click="mode = 'list'"
          >
            {{ t('tasks.backList') }}
          </button>
        </div>
      </div>

      <div v-if="error" class="mb-4 p-4 rounded-xl border border-[#ff4d6d]/30 bg-[#ff4d6d]/10 text-[#ff8a9e] text-sm">
        {{ error }}
      </div>
      <div v-if="success" class="mb-4 p-4 rounded-xl border border-[#3dd6c6]/30 bg-[#3dd6c6]/10 text-[#3dd6c6] text-sm">
        {{ success }}
      </div>

      <!-- LIST -->
      <div v-if="mode === 'list'">
        <div class="flex flex-wrap gap-2 mb-6">
          <button
            type="button"
            class="px-3 py-1.5 rounded-md text-xs border font-mono"
            :class="filterTrack === 'all'
              ? 'border-[#ff5c33]/50 bg-[#ff5c33]/15 text-[#ff8a66]'
              : 'border-white/10 text-[#7a7368]'"
            @click="filterTrack = 'all'"
          >
            {{ t('tracks.all') }}
          </button>
          <button
            v-for="tr in store.tracks"
            :key="tr.id"
            type="button"
            class="px-3 py-1.5 rounded-md text-xs border font-mono"
            :class="filterTrack === tr.id
              ? 'border-[#ff5c33]/50 bg-[#ff5c33]/15 text-[#ff8a66]'
              : 'border-white/10 text-[#7a7368]'"
            @click="filterTrack = tr.id"
          >
            {{ trackLabel(tr) }}
          </button>
        </div>

        <div v-if="!filteredTasks.length" class="glass-card p-10 text-center text-[#7a7368]">
          {{ t('tasks.empty') }}
        </div>

        <div v-else class="space-y-3">
          <article
            v-for="task in filteredTasks"
            :key="task.id"
            class="glass-card p-5 flex flex-col md:flex-row md:items-center gap-4"
          >
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2 mb-1">
                <h3 class="font-display font-bold text-lg tracking-tight truncate">{{ task.name }}</h3>
                <span class="font-mono text-[10px] px-2 py-0.5 rounded-full border border-white/10 text-[#9a9488]">
                  {{ task.id }}
                </span>
                <span
                  v-if="task.custom"
                  class="font-mono text-[10px] px-2 py-0.5 rounded-full border border-[#3dd6c6]/30 text-[#3dd6c6] bg-[#3dd6c6]/10"
                >
                  custom
                </span>
              </div>
              <p class="text-sm text-[#9a9488] line-clamp-2">{{ task.description }}</p>
              <div class="mt-2 font-mono text-[11px] text-[#7a7368] flex flex-wrap gap-2">
                <span>{{ task.track || '—' }}</span>
                <span>·</span>
                <span>{{ task.language }}</span>
                <span>·</span>
                <span>{{ task.type }}</span>
                <span>·</span>
                <span>{{ task.difficulty }}</span>
                <span>·</span>
                <span>{{ task.testCases || 0 }} tests</span>
              </div>
            </div>
            <div class="flex flex-wrap gap-2 shrink-0">
              <button type="button" class="btn-secondary !py-1.5 !px-3 !text-xs" @click="openEdit(task)">
                {{ t('tasks.edit') }}
              </button>
              <button type="button" class="btn-secondary !py-1.5 !px-3 !text-xs" @click="goArena(task.id)">
                {{ t('tasks.useInArena') }}
              </button>
              <button
                type="button"
                class="!py-1.5 !px-3 !text-xs rounded-md border border-[#ff4d6d]/35 text-[#ff8a9e] hover:bg-[#ff4d6d]/10"
                @click="removeTask(task)"
              >
                {{ t('tasks.delete') }}
              </button>
            </div>
          </article>
        </div>
      </div>

      <!-- CREATE / EDIT FORM -->
      <div v-else class="space-y-5">
        <div v-if="loadingDetail" class="text-[#7a7368]">{{ t('tasks.loading') }}</div>

        <div v-if="mode === 'create'" class="glass-card p-5">
          <div class="font-display font-bold mb-3">{{ t('tasks.templates') }}</div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              type="button"
              class="px-3 py-2 rounded-lg text-xs border border-white/10 hover:border-[#ff5c33]/40 font-mono text-[#b8b0a2] hover:text-[#f3efe6]"
              @click="applyTemplate(tpl.id)"
            >
              {{ tpl.label }}
            </button>
          </div>
          <p class="text-[11px] text-[#7a7368] mt-3">{{ t('tasks.templateHint') }}</p>
        </div>

        <div class="glass-card p-5 md:p-6 space-y-4">
          <div class="grid md:grid-cols-2 gap-4">
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">id</span>
              <input
                v-model="formId"
                class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm font-mono"
                :disabled="mode === 'edit'"
                placeholder="custom-my-task"
              >
            </label>
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">name</span>
              <input
                v-model="formName"
                class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm"
                placeholder="My Task"
              >
            </label>
          </div>

          <label class="block">
            <span class="text-xs font-mono text-[#7a7368]">description</span>
            <textarea
              v-model="formDescription"
              rows="5"
              class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm leading-relaxed"
              :placeholder="t('tasks.descPlaceholder')"
            />
          </label>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">track</span>
              <select v-model="formTrack" class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-2 py-2 text-sm">
                <option v-for="tr in store.tracks" :key="tr.id" :value="tr.id">{{ tr.id }}</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">language</span>
              <select v-model="formLanguage" class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-2 py-2 text-sm">
                <option value="python">python</option>
                <option value="html">html</option>
                <option value="typescript">typescript</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">type</span>
              <select v-model="formType" class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-2 py-2 text-sm">
                <option value="feature">feature</option>
                <option value="bugfix">bugfix</option>
                <option value="algorithm">algorithm</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-mono text-[#7a7368]">difficulty</span>
              <select v-model="formDifficulty" class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-2 py-2 text-sm">
                <option value="easy">easy</option>
                <option value="medium">medium</option>
                <option value="hard">hard</option>
              </select>
            </label>
          </div>

          <div class="grid md:grid-cols-2 gap-4">
            <div>
              <label class="block mb-1">
                <span class="text-xs font-mono text-[#7a7368]">{{ t('tasks.starterFile') }}</span>
                <input
                  v-model="starterName"
                  class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-1.5 text-xs font-mono"
                >
              </label>
              <textarea
                v-model="starterCode"
                rows="14"
                class="w-full rounded-lg bg-[#0c0a08] border border-white/10 px-3 py-2 text-[12px] font-mono leading-relaxed"
                spellcheck="false"
              />
            </div>
            <div>
              <label class="block mb-1">
                <span class="text-xs font-mono text-[#7a7368]">{{ t('tasks.testFile') }}</span>
                <input
                  v-model="testName"
                  class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-1.5 text-xs font-mono"
                >
              </label>
              <textarea
                v-model="testCode"
                rows="14"
                class="w-full rounded-lg bg-[#0c0a08] border border-white/10 px-3 py-2 text-[12px] font-mono leading-relaxed"
                spellcheck="false"
              />
            </div>
          </div>

          <label class="block">
            <span class="text-xs font-mono text-[#7a7368]">{{ t('tasks.extraFiles') }}</span>
            <textarea
              v-model="extraFilesJson"
              rows="4"
              class="mt-1 w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-xs font-mono"
              spellcheck="false"
            />
          </label>

          <p class="text-[11px] text-[#7a7368] leading-relaxed">
            {{ t('tasks.saveHint') }}
          </p>

          <div class="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              class="btn-primary !py-2.5 !px-5"
              :disabled="!canSave"
              @click="saveTask"
            >
              {{ saving ? t('tasks.saving') : (mode === 'edit' ? t('tasks.saveEdit') : t('tasks.saveCreate')) }}
            </button>
            <button type="button" class="btn-secondary !py-2.5 !px-5" @click="mode = 'list'">
              {{ t('tasks.backList') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
