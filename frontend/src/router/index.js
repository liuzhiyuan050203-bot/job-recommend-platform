import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { roleHome } from '@/utils/role'

import Home from '@/views/Home.vue'
import StudentLayout from '@/layouts/StudentLayout.vue'
import CompanyLayout from '@/layouts/CompanyLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

const Placeholder = () => import('@/views/Placeholder.vue')

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: '首页', public: true }
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
        component: Placeholder,
        meta: { title: '首页', desc: '学生首页将展示推荐职位、技能雷达与求职进度' }
      },
      {
        path: 'jobs',
        name: 'StudentJobs',
        component: () => import('@/views/student/JobList.vue'),
        meta: { title: '职位搜索' }
      },
      {
        path: 'favorites',
        name: 'StudentFavorites',
        component: Placeholder,
        meta: { title: '我的收藏', desc: '收藏的职位将在这里集中查看' }
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
        component: Placeholder,
        meta: { title: '个人档案与技能', desc: '个人档案、学历信息与技能标签将在这里维护' }
      },
      {
        path: 'community',
        name: 'StudentCommunity',
        component: Placeholder,
        meta: { title: '面经社区', desc: '面经与企业评价社区将在这里开放' }
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
        component: Placeholder,
        meta: { title: '企业资料与资质', desc: '企业基本资料、营业执照与资质提交将在这里完成' }
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
        component: Placeholder,
        meta: { title: '面试安排', desc: '面试日程与提醒将在这里安排' }
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
        component: Placeholder,
        meta: { title: '企业审核', desc: '企业资质审核将在这里处理' }
      },
      {
        path: 'jobs',
        name: 'AdminJobs',
        component: Placeholder,
        meta: { title: '职位审核', desc: '职位合规审核将在这里处理' }
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
        component: Placeholder,
        meta: { title: '轮播图', desc: '首页轮播图将在这里配置' }
      },
      {
        path: 'articles',
        name: 'AdminArticles',
        component: Placeholder,
        meta: { title: '文章', desc: '双选会公告、就业政策与资讯将在这里发布' }
      },
      {
        path: 'categories',
        name: 'AdminCategories',
        component: Placeholder,
        meta: { title: '职位分类', desc: '职位分类树将在这里维护' }
      },
      {
        path: 'skills',
        name: 'AdminSkills',
        component: Placeholder,
        meta: { title: '技能标签', desc: '技能标签字典将在这里维护' }
      },
      {
        path: 'applications',
        name: 'AdminApplications',
        component: Placeholder,
        meta: { title: '投递总览', desc: '全平台投递记录将在这里查看' }
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
