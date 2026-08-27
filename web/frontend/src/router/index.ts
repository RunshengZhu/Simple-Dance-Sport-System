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
        path: 'users',
        name: 'Users',
        component: () => import('@/views/users/List.vue'),
        meta: { title: '用户管理', roles: ['admin'] }
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/logs/List.vue'),
        meta: { title: '操作日志', roles: ['admin'] }
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
    path: '/judge/competitions/:id/events/:eventId/scoring',
    name: 'JudgeScoring',
    component: () => import('@/views/judge/Scoring.vue'),
    meta: { title: '裁判评分', requiresAuth: true, roles: ['admin', 'judge'] }
  },
  {
    path: '/public/competitions',
    name: 'PublicCompetitions',
    component: () => import('@/views/public/Viewer.vue'),
    meta: { title: '公众查询', requiresAuth: false }
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
  const requiresAuth = to.meta.requiresAuth !== false
  const allowedRoles = to.meta.roles as string[] | undefined

  if (requiresAuth && !userStore.token) {
    next('/login')
    return
  }

  if (userStore.token && to.path === '/login') {
    next('/')
    return
  }

  if (allowedRoles && userStore.role && !allowedRoles.includes(userStore.role)) {
    next('/dashboard')
    return
  }

  next()
})

export default router
