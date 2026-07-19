import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LeaderboardView from '../views/LeaderboardView.vue'
import ArenaView from '../views/ArenaView.vue'
import ComparisonView from '../views/ComparisonView.vue'
import ModelConfigView from '../views/ModelConfigView.vue'
import OutputsView from '../views/OutputsView.vue'
import TasksView from '../views/TasksView.vue'
import { ROUTE_SEO, applyPageSeo } from '../composables/usePageSeo'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { seoKey: 'home' },
    },
    {
      path: '/leaderboard',
      name: 'leaderboard',
      component: LeaderboardView,
      meta: { seoKey: 'leaderboard' },
    },
    {
      path: '/arena',
      name: 'arena',
      component: ArenaView,
      meta: { seoKey: 'arena' },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: TasksView,
      meta: { seoKey: 'tasks' },
    },
    {
      path: '/comparison',
      name: 'comparison',
      component: ComparisonView,
      meta: { seoKey: 'comparison' },
    },
    {
      path: '/outputs',
      name: 'outputs',
      component: OutputsView,
      meta: { seoKey: 'outputs' },
    },
    {
      path: '/models',
      name: 'models',
      component: ModelConfigView,
      meta: { seoKey: 'models' },
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.afterEach((to) => {
  const key = String(to.meta.seoKey || to.name || 'home')
  const pack = ROUTE_SEO[key]
  if (!pack) return
  const locale = (localStorage.getItem('locale') || document.documentElement.lang || 'zh').startsWith('en')
    ? 'en'
    : 'zh'
  applyPageSeo(pack[locale])
})

export default router
