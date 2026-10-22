import { createRouter, createWebHistory } from 'vue-router'
import AnalyzeView from '../views/AnalyzeView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'analyze', component: AnalyzeView },
    {
      path: '/reports/:id',
      name: 'report',
      component: () => import('../views/ReportView.vue'),
      props: true,
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('../views/LibraryView.vue'),
    },
    {
      path: '/history/:market/:ticker',
      name: 'history',
      component: () => import('../views/HistoryView.vue'),
      props: true,
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (to) => (to.hash ? { el: to.hash, top: 80, behavior: 'smooth' } : { top: 0 }),
})
