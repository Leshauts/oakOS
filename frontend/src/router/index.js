import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  // D'autres routes seront ajoutées ultérieurement
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;