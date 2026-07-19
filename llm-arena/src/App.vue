<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
</script>

<template>
  <div class="arena-stage min-h-screen">
    <div class="arena-content min-h-screen flex flex-col">
      <AppHeader />
      <main class="flex-1 pt-[4.5rem]">
        <RouterView v-slot="{ Component, route }">
          <transition name="page" mode="out-in">
            <component :is="Component" :key="route.path" />
          </transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>
