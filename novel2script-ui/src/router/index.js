import { createRouter, createWebHistory } from 'vue-router'
import WorkbenchView from '@/views/WorkbenchView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'workbench',
      component: WorkbenchView,
    },
  ],
})

export default router
