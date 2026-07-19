<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArenaStore } from '@/stores/arena'
import type { Model, ModelProvider } from '@/types'

const store = useArenaStore()
const { t } = useI18n()
const syncing = ref(false)
const syncMsg = ref<string | null>(null)

onMounted(async () => {
  try {
    await store.syncKeysFromEnv()
  } catch {
    // backend offline — keep localStorage keys
  }
})

async function pullFromEnv() {
  syncing.value = true
  syncMsg.value = null
  try {
    const r = await store.syncKeysFromEnv()
    const n = Object.values(r.providers || {}).filter((p: { has_key?: boolean }) => p.has_key).length
    syncMsg.value = t('modelConfig.pulledFromEnv', { n })
  } catch (e) {
    syncMsg.value = e instanceof Error ? e.message : 'Pull failed'
  } finally {
    syncing.value = false
  }
}

async function pushToEnv() {
  syncing.value = true
  syncMsg.value = null
  try {
    const r = await store.syncKeysToEnv()
    syncMsg.value = t('modelConfig.pushedToEnv', { keys: (r.updated_keys || []).join(', ') })
  } catch (e) {
    syncMsg.value = e instanceof Error ? e.message : 'Push failed'
  } finally {
    syncing.value = false
  }
}

// Dialog state
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const editingModel = ref<Model | null>(null)

// Form state
const form = ref({
  name: '',
  provider: 'anthropic',
  version: '',
  description: '',
  color: '#3b82f6',
  apiKey: '',
  baseUrl: '',
  temperature: 0.0,
  maxTokens: 4096,
})

// Provider colors
const providerColors: Record<string, string> = {
  anthropic: '#d97757',
  openai: '#10a37f',
  google: '#4285f4',
  deepseek: '#4f46e5',
  custom: '#8b5cf6',
}

const providerOptions = computed(() =>
  store.providers.map(p => ({ value: p.id, label: p.name }))
)

const selectedProvider = computed(() =>
  store.providers.find(p => p.id === form.value.provider)
)

function openAddDialog() {
  form.value = {
    name: '',
    provider: 'anthropic',
    version: '',
    description: '',
    color: '#3b82f6',
    apiKey: '',
    baseUrl: '',
    temperature: 0.0,
    maxTokens: 4096,
  }
  showAddDialog.value = true
}

function openEditDialog(model: Model) {
  editingModel.value = model
  form.value = {
    name: model.name,
    provider: model.provider,
    version: model.version,
    description: model.description,
    color: model.color,
    apiKey: model.apiKey || '',
    baseUrl: model.baseUrl || '',
    temperature: model.temperature || 0.0,
    maxTokens: model.maxTokens || 4096,
  }
  showEditDialog.value = true
}

async function saveModel() {
  if (!form.value.name || !form.value.version) return

  const modelData = {
    name: form.value.name,
    provider: form.value.provider,
    version: form.value.version,
    description: form.value.description,
    color: form.value.color,
    apiKey: form.value.apiKey || undefined,
    baseUrl: form.value.baseUrl || undefined,
    temperature: form.value.temperature,
    maxTokens: form.value.maxTokens,
    enabled: true,
  }

  if (showEditDialog.value && editingModel.value) {
    store.updateModel(editingModel.value.id, modelData)
  } else {
    store.addModel(modelData)
  }

  // Also write this provider's key to .env when present
  if (form.value.apiKey || form.value.baseUrl) {
    try {
      await store.syncKeysToEnv()
      syncMsg.value = t('modelConfig.savedAndEnv')
    } catch {
      syncMsg.value = t('modelConfig.savedLocalOnly')
    }
  }

  showAddDialog.value = false
  showEditDialog.value = false
  editingModel.value = null
}

function confirmDelete(model: Model) {
  if (confirm(`Are you sure you want to delete "${model.name}"?`)) {
    store.deleteModel(model.id)
  }
}

function getProviderColor(providerId: string): string {
  return providerColors[providerId] || '#6b7280'
}

function getProviderName(providerId: string): string {
  const provider = store.providers.find(p => p.id === providerId)
  return provider?.name || providerId
}
</script>

<template>
  <div class="min-h-screen py-24 px-6">
    <div class="max-w-7xl mx-auto">
      <!-- Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 class="text-4xl md:text-5xl font-bold mb-4">
            <span class="gradient-text">{{ t('modelConfig.title') }}</span>
          </h1>
          <p class="text-kimi-muted text-lg">
            {{ t('modelConfig.subtitle') }}
          </p>
          <p class="text-xs text-kimi-muted mt-2">{{ t('modelConfig.envSyncHint') }}</p>
          <p v-if="syncMsg" class="text-sm text-emerald-400 mt-2">{{ syncMsg }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="px-4 py-2 rounded-xl border border-kimi-border text-sm text-kimi-text hover:bg-kimi-surface disabled:opacity-50"
            :disabled="syncing"
            @click="pullFromEnv"
          >
            {{ t('modelConfig.pullFromEnv') }}
          </button>
          <button
            type="button"
            class="px-4 py-2 rounded-xl border border-kimi-border text-sm text-kimi-text hover:bg-kimi-surface disabled:opacity-50"
            :disabled="syncing"
            @click="pushToEnv"
          >
            {{ t('modelConfig.pushToEnv') }}
          </button>
          <button class="btn-primary flex items-center gap-2" type="button" @click="openAddDialog">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            {{ t('modelConfig.addModel') }}
          </button>
        </div>
      </div>

      <!-- Models Grid -->
      <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="model in store.models"
          :key="model.id"
          class="glass-card p-6 group"
          :class="{ 'opacity-50': !model.enabled }"
        >
          <div class="flex items-start justify-between mb-4">
            <div class="flex items-center gap-3">
              <div
                class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
                :style="{ backgroundColor: model.color }"
              >
                {{ model.name.charAt(0) }}
              </div>
              <div>
                <h3 class="font-semibold text-kimi-text">{{ model.name }}</h3>
                <p class="text-xs text-kimi-muted">{{ getProviderName(model.provider) }}</p>
              </div>
            </div>
            <div class="flex items-center gap-1">
              <!-- Enable/Disable toggle -->
              <button
                class="p-1.5 rounded-lg text-kimi-muted hover:text-kimi-text transition-colors"
                :title="model.enabled ? 'Disable' : 'Enable'"
                @click="store.toggleModelEnabled(model.id)"
              >
                <svg v-if="model.enabled" class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728m-9.9-2.829a5 5 0 010-7.07m7.072 7.07a5 5 0 01-7.072 0" />
                </svg>
                <svg v-else class="w-4 h-4 text-kimi-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
              </button>
              <!-- Edit button -->
              <button
                class="p-1.5 rounded-lg text-kimi-muted hover:text-blue-400 transition-colors"
                @click="openEditDialog(model)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
              <!-- Delete button (only for custom models) -->
              <button
                v-if="model.custom"
                class="p-1.5 rounded-lg text-kimi-muted hover:text-rose-400 transition-colors"
                @click="confirmDelete(model)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>

          <p class="text-sm text-kimi-muted mb-4">{{ model.description }}</p>

          <div class="flex items-center gap-2 text-xs text-kimi-muted flex-wrap">
            <span class="px-2 py-1 rounded-lg bg-kimi-surface">{{ model.version }}</span>
            <span v-if="model.custom" class="px-2 py-1 rounded-lg bg-violet-500/10 text-violet-400">Custom</span>
            <span
              v-if="model.apiKey"
              class="px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400"
              title="API key saved in this browser"
            >
              Key configured
            </span>
            <span
              v-else-if="store.providers.find(p => p.id === model.provider)?.requiresApiKey"
              class="px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400"
              title="Edit model to set API key"
            >
              No key
            </span>
            <span v-if="!model.enabled" class="px-2 py-1 rounded-lg bg-kimi-surface text-kimi-muted">Disabled</span>
          </div>
        </div>
      </div>

      <!-- Add/Edit Dialog -->
      <div
        v-if="showAddDialog || showEditDialog"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showAddDialog = false; showEditDialog = false" />
        <div class="relative glass-card w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
          <h2 class="text-xl font-bold mb-6">
            {{ showEditDialog ? 'Edit Model' : 'Add Model' }}
          </h2>

          <form @submit.prevent="saveModel">
            <div class="space-y-4">
              <!-- Name -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Model Name</label>
                <input
                  v-model="form.name"
                  type="text"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                  placeholder="e.g., My Custom Model"
                  required
                />
              </div>

              <!-- Provider -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Provider</label>
                <select
                  v-model="form.provider"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                >
                  <option v-for="option in providerOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>

              <!-- Version -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Model Version</label>
                <input
                  v-model="form.version"
                  type="text"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                  placeholder="e.g., gpt-4o"
                  required
                />
              </div>

              <!-- Description -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Description</label>
                <textarea
                  v-model="form.description"
                  rows="2"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors resize-none"
                  placeholder="Brief description of the model"
                />
              </div>

              <!-- Color -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Color</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model="form.color"
                    type="color"
                    class="w-12 h-10 rounded-xl bg-kimi-surface border border-kimi-border cursor-pointer"
                  />
                  <span class="text-sm text-kimi-muted">{{ form.color }}</span>
                </div>
              </div>

              <!-- API Key (optional) -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">
                  API Key
                  <span class="text-xs text-kimi-muted">(optional - uses env var if empty)</span>
                </label>
                <input
                  v-model="form.apiKey"
                  type="password"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                  placeholder="sk-..."
                />
              </div>

              <!-- Base URL (for custom providers) -->
              <div v-if="selectedProvider?.supportsBaseUrl">
                <label class="block text-sm font-medium text-kimi-muted mb-1">Base URL</label>
                <input
                  v-model="form.baseUrl"
                  type="text"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                  :placeholder="selectedProvider?.defaultBaseUrl || 'https://api.example.com/v1'"
                />
              </div>

              <!-- Temperature -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">
                  Temperature: {{ form.temperature }}
                </label>
                <input
                  v-model.number="form.temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  class="w-full"
                />
              </div>

              <!-- Max Tokens -->
              <div>
                <label class="block text-sm font-medium text-kimi-muted mb-1">Max Tokens</label>
                <input
                  v-model.number="form.maxTokens"
                  type="number"
                  class="w-full px-4 py-2 rounded-xl bg-kimi-surface border border-kimi-border text-kimi-text focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
                  placeholder="4096"
                />
              </div>
            </div>

            <div class="flex gap-3 mt-6">
              <button type="submit" class="btn-primary flex-1">
                {{ showEditDialog ? 'Save Changes' : 'Add Model' }}
              </button>
              <button
                type="button"
                class="btn-secondary flex-1"
                @click="showAddDialog = false; showEditDialog = false"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
