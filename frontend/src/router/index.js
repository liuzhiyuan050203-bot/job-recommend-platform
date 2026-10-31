import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { roleHome } from '@/utils/role'

import Home from '@/views/Home.vue'
import StudentLayout from '@/layouts/StudentLayout.vue'
import CompanyLayout from '@/layouts/CompanyLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: '首页', public: true }
  },
  {
    path: '/articles',
    name: 'ArticleList',
    component: () => import('@/views/ArticleList.vue'),
    meta: { title: '校园资讯与政策公告', public: true }
  },
  {
    path: '/articles/:id',
    name: 'ArticleDetail',
    component: () => import('@/views/ArticleDetail.vue'),
    meta: { title: '文章详情', public: true }
  },
  {
    path: '/community',
    name: 'CommunityList',
    component: () => import('@/views/CommunityList.vue'),
    meta: { title: '面经与企业评价社区', public: true }
  },
  {
    path: '/community/:id',
    name: 'PostDetail',
    component: () => import('@/views/PostDetail.vue'),
    meta: { title: '面经详情', public: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册', public: true }
  },
  {
    path: '/student',
    component: StudentLayout,
    redirect: '/student/home',
    meta: { title: '学生端', roles: ['student'] },
    children: [
      {
        path: 'home',
        name: 'StudentHome',
        component: () => import('@/views/student/Home.vue'),
        meta: { title: '首页' }
      },
      {
        path: 'dashboard',
        name: 'StudentDashboard',
        component: () => import('@/views/student/Dashboard.vue'),
        meta: { title: '求职看板' }
      },
      {
        path: 'jobs',
        name: 'StudentJobs',
        component: () => import('@/views/student/JobList.vue'),
        meta: { title: '职位搜索' }
      },
      {
        path: 'recommend',
        name: 'StudentRecommend',
        component: () => import('@/views/student/Recommend.vue'),
        meta: { title: '为你推荐' }
      },
      {
        path: 'assistant',
        name: 'StudentAssistant',
        component: () => import('@/views/student/AiAssistant.vue'),
        meta: { title: '就业助手' }
      },
      {
        path: 'jobs/:id',
        name: 'StudentJobDetail',
        component: () => import('@/views/student/JobDetail.vue'),
        meta: { title: '职位详情', activeMenu: '/student/jobs' }
      },
      {
        path: 'favorites',
        name: 'StudentFavorites',
        component: () => import('@/views/student/Favorites.vue'),
        meta: { title: '我的收藏' }
      },
      {
        path: 'applications',
        name: 'StudentApplications',
        component: () => import('@/views/student/Applications.vue'),
        meta: { title: '我的投递' }
      },
      {
        path: 'resume',
        name: 'StudentResume',
        component: () => import('@/views/student/Resume.vue'),
        meta: { title: '在线简历' }
      },
      {
        path: 'profile',
        name: 'StudentProfile',
        component: () => import('@/views/student/Profile.vue'),
        meta: { title: '个人档案与技能' }
      },
      {
        path: 'community',
        name: 'StudentCommunity',
        component: () => import('@/views/student/MyPosts.vue'),
        meta: { title: '面经社区' }
      }
    ]
  },
  {
    path: '/company',
    component: CompanyLayout,
    redirect: () => {
      const userStore = useUserStore()
      if (userStore.roleName === 'company' && Number(userStore.companyAuditStatus) !== 1) {
        return '/company/profile'
      }
      return '/company/jobs'
    },
    meta: { title: '企业端', roles: ['company'] },
    children: [
      {
        path: 'profile',
        name: 'CompanyProfile',
        component: () => import('@/views/company/Profile.vue'),
        meta: { title: '企业资料与资质' }
      },
      {
        path: 'dashboard',
        name: 'CompanyDashboard',
        component: () => import('@/views/company/Dashboard.vue'),
        meta: { title: '招聘看板' }
      },
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
        path: 'interviews',
        name: 'CompanyInterviews',
        component: () => import('@/views/company/Interviews.vue'),
        meta: { title: '面试安排' }
      },
      {
        path: 'assistant',
        name: 'CompanyAssistant',
        component: () => import('@/views/company/AiAssistant.vue'),
        meta: { title: '招聘助手' }
      }
    ]
  },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: '/admin/users',
    meta: { title: '管理员端', roles: ['admin'] },
    children: [
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/UserAudit.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'companies',
        name: 'AdminCompanies',
        component: () => import('@/views/admin/CompanyAudit.vue'),
        meta: { title: '企业审核' }
      },
      {
        path: 'jobs',
        name: 'AdminJobs',
        component: () => import('@/views/admin/JobAudit.vue'),
        meta: { title: '职位审核' }
      },
      {
        path: 'content',
        name: 'AdminContent',
        component: () => import('@/views/admin/ContentManage.vue'),
        meta: { title: '内容审核' }
      },
      {
        path: 'banners',
        name: 'AdminBanners',
        component: () => import('@/views/admin/BannerManage.vue'),
        meta: { title: '轮播图' }
      },
      {
        path: 'articles',
        name: 'AdminArticles',
        component: () => import('@/views/admin/ArticleManage.vue'),
        meta: { title: '文章' }
      },
      {
        path: 'categories',
        name: 'AdminCategories',
        component: () => import('@/views/admin/CategoryManage.vue'),
        meta: { title: '职位分类' }
      },
      {
        path: 'skills',
        name: 'AdminSkills',
        component: () => import('@/views/admin/SkillTagManage.vue'),
        meta: { title: '技能标签' }
      },
      {
        path: 'applications',
        name: 'AdminApplications',
        component: () => import('@/views/admin/ApplicationOverview.vue'),
        meta: { title: '投递总览' }
      },
      {
        path: 'analytics',
        name: 'AdminAnalytics',
        component: () => import('@/views/admin/Analytics.vue'),
        meta: { title: '就业分析' }
      },
      {
        path: 'recommend',
        name: 'AdminRecommend',
        component: () => import('@/views/admin/Recommend.vue'),
        meta: { title: '推荐评估' }
      },
      {
        path: 'assistant',
        name: 'AdminAssistant',
        component: () => import('@/views/admin/AiAssistant.vue'),
        meta: { title: '数据助手' }
      },
      {
        path: 'knowledge',
        name: 'AdminKnowledge',
        component: () => import('@/views/admin/Knowledge.vue'),
        meta: { title: '知识库管理' }
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
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

function allowsCompanyPath(path) {
  return path === '/company/profile' || path.startsWith('/company/profile/')
}

router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} · 高校就业推荐平台` : '高校就业推荐平台'

  const userStore = useUserStore()
  const isPublic = to.meta.public || to.matched.some((record) => record.meta.public)

  if (isPublic) {
    const authPage = to.path === '/login' || to.path === '/register'
    if (authPage && userStore.isLoggedIn) {
      next(roleHome(userStore.roleName))
      return
    }
    next()
    return
  }

  if (!userStore.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  const requiredRoles = to.matched.flatMap((record) => record.meta.roles || [])
  if (requiredRoles.length > 0 && !requiredRoles.includes(userStore.roleName)) {
    next(roleHome(userStore.roleName))
    return
  }

  if (userStore.roleName === 'company' && Number(userStore.companyAuditStatus) !== 1) {
    if (to.path.startsWith('/company') && !allowsCompanyPath(to.path)) {
      next('/company/profile')
      return
    }
  }

  next()
})

export default router
