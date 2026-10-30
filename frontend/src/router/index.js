import { createRouter, createWebHistory } from 'vue-router'

import Home from '@/views/Home.vue'
import StudentLayout from '@/layouts/StudentLayout.vue'
import CompanyLayout from '@/layouts/CompanyLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: '首页' }
  },
  {
    path: '/student',
    component: StudentLayout,
    redirect: '/student/jobs',
    meta: { title: '学生端' },
    children: [
      {
        path: 'jobs',
        name: 'StudentJobs',
        component: () => import('@/views/student/JobList.vue'),
        meta: { title: '职位检索' }
      },
      {
        path: 'resume',
        name: 'StudentResume',
        component: () => import('@/views/student/Resume.vue'),
        meta: { title: '我的简历' }
      },
      {
        path: 'applications',
        name: 'StudentApplications',
        component: () => import('@/views/student/Applications.vue'),
        meta: { title: '投递记录' }
      }
    ]
  },
  {
    path: '/company',
    component: CompanyLayout,
    redirect: '/company/jobs',
    meta: { title: '企业端' },
    children: [
      {
        path: 'jobs',
        name: 'CompanyJobs',
        component: () => import('@/views/company/JobManage.vue'),
        meta: { title: '职位管理' }
      },
      {
        path: 'candidates',
        name: 'CompanyCandidates',
        component: () => import('@/views/company/Candidates.vue'),
        meta: { title: '候选人管理' }
      },
      {
        path: 'dashboard',
        name: 'CompanyDashboard',
        component: () => import('@/views/company/Dashboard.vue'),
        meta: { title: '数据看板' }
      }
    ]
  },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: '/admin/users',
    meta: { title: '管理员端' },
    children: [
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/UserAudit.vue'),
        meta: { title: '用户审核' }
      },
      {
        path: 'content',
        name: 'AdminContent',
        component: () => import('@/views/admin/ContentManage.vue'),
        meta: { title: '内容管理' }
      },
      {
        path: 'analytics',
        name: 'AdminAnalytics',
        component: () => import('@/views/admin/Analytics.vue'),
        meta: { title: '数据大屏' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} · 高校就业推荐平台`
  }
  next()
})

export default router
