import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页', icon: 'HomeFilled' }
      },
      {
        path: 'competitions',
        name: 'Competitions',
        component: () => import('@/views/competitions/List.vue'),
        meta: { title: '赛事管理' }
      },
      {
        path: 'competitions/:id',
        name: 'CompetitionDetail',
        component: () => import('@/views/competitions/Detail.vue'),
        meta: { title: '赛事详情' }
      },
      {
        path: 'competitions/:id/competitors',
        name: 'Competitors',
        component: () => import('@/views/competitions/Competitors.vue'),
        meta: { title: '选手管理' }
      },
      {
        path: 'competitions/:id/events',
        name: 'Events',
        component: () => import('@/views/events/List.vue'),
        meta: { title: '场次管理' }
      },
      {
        path: 'competitions/:id/scoring/:eventId',
        name: 'Scoring',
        component: () => import('@/views/scoring/Index.vue'),
        meta: { title: '评分' }
      },
      {
        path: 'competitions/:id/ranking',
        name: 'Ranking',
        component: () => import('@/views/ranking/Index.vue'),
        meta: { title: '单位总分' }
      },
      {
        path: 'competitions/:id/awards',
        name: 'Awards',
        component: () => import('@/views/ranking/Awards.vue'),
        meta: { title: '奖项配置' }
      }
    ]
  },
  {
    path: '/display/:type',
    name: 'Display',
    component: () => import('@/views/display/Index.vue'),
    meta: { title: '大屏展示' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.path !== '/login' && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
