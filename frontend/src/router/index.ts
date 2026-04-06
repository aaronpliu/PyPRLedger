import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  // Auth routes
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { requiresAuth: false },
  },

  // Main app routes
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
      },
      {
        path: 'reviews',
        name: 'Reviews',
        component: () => import('@/views/reviews/ReviewListView.vue'),
      },
      {
        path: 'reviews/:id',
        name: 'ReviewDetail',
        component: () => import('@/views/reviews/ReviewDetailView.vue'),
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/auth/ProfileView.vue'),
      },
      {
        path: 'scores',
        name: 'ScoreList',
        component: () => import('@/views/scores/ScoreListView.vue'),
      },
      {
        path: 'scores/analytics',
        name: 'ScoreAnalytics',
        component: () => import('@/views/scores/ScoreAnalyticsView.vue'),
      },
    ],
  },

  // Admin routes
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('@/views/admin/UserManagementView.vue'),
      },
      {
        path: 'roles',
        name: 'RoleManagement',
        component: () => import('@/views/admin/RoleManagementView.vue'),
      },
      {
        path: 'audit',
        name: 'AuditLogs',
        component: () => import('@/views/admin/AuditLogView.vue'),
      },
    ],
  },

  // Error routes
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/errors/ForbiddenView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/errors/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // Check if route requires authentication
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  // Check if route requires admin
  if (to.meta.requiresAdmin) {
    // TODO: Implement admin check based on user roles
    // For now, allow access if authenticated
    if (!authStore.isAuthenticated) {
      next('/login')
      return
    }
  }

  // Redirect to dashboard if already logged in and trying to access auth pages
  if ((to.path === '/login' || to.path === '/register') && authStore.isAuthenticated) {
    next('/')
    return
  }

  next()
})

export default router
