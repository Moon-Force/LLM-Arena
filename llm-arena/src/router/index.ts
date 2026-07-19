import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LeaderboardView from '../views/LeaderboardView.vue'
import ArenaView from '../views/ArenaView.vue'
import ComparisonView from '../views/ComparisonView.vue'
import ModelConfigView from '../views/ModelConfigView.vue'
import OutputsView from '../views/OutputsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/leaderboard',
      name: 'leaderboard',
      component: LeaderboardView,
    },
    {
      path: '/arena',
      name: 'arena',
      component: ArenaView,
    },
    {
      path: '/comparison',
      name: 'comparison',
      component: ComparisonView,
    },
    {
      path: '/outputs',
      name: 'outputs',
      component: OutputsView,
    },
    {
      path: '/models',
      name: 'models',
      component: ModelConfigView,
    },
  ],
})

export default router
