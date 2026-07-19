<script setup lang="ts">
import type { FileTreeNode } from '@/utils/api'
import FileTree from './FileTree.vue'

defineProps<{
  nodes: FileTreeNode[]
  active?: string | null
  depth?: number
}>()

const emit = defineEmits<{
  select: [path: string]
}>()
</script>

<template>
  <ul class="space-y-0.5">
    <li v-for="n in nodes" :key="n.path">
      <button
        v-if="n.type === 'file'"
        type="button"
        class="w-full text-left px-1.5 py-0.5 rounded truncate"
        :class="active === n.path ? 'bg-blue-500/20 text-blue-300' : 'text-kimi-muted hover:text-kimi-text'"
        :style="{ paddingLeft: `${(depth || 0) * 8 + 4}px` }"
        @click="emit('select', n.path)"
      >
        {{ n.preview ? '🖥' : '📄' }} {{ n.name }}
      </button>
      <div v-else>
        <div
          class="text-kimi-muted/80 px-1.5 py-0.5 truncate"
          :style="{ paddingLeft: `${(depth || 0) * 8 + 4}px` }"
        >
          📁 {{ n.name }}
        </div>
        <FileTree
          v-if="n.children?.length"
          :nodes="n.children"
          :active="active"
          :depth="(depth || 0) + 1"
          @select="(p) => emit('select', p)"
        />
      </div>
    </li>
  </ul>
</template>
