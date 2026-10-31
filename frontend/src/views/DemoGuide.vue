<template>
  <div class="demo-page">
    <header class="top-bar">
      <div class="brand" @click="router.push('/')">高校就业推荐平台</div>
      <nav class="top-nav">
        <el-button link @click="router.push('/')">首页</el-button>
        <el-button link @click="router.push('/articles')">就业资讯与公告</el-button>
        <el-button link @click="router.push('/community')">求职面经社区</el-button>
        <el-button link type="primary">系统演示</el-button>
      </nav>
      <div class="top-actions">
        <template v-if="userStore.isLoggedIn">
          <span class="welcome">你好，{{ userStore.nickname }}</span>
          <el-button type="primary" @click="goWorkspace">进入工作台</el-button>
        </template>
        <el-button v-else @click="router.push('/login')">登录</el-button>
      </div>
    </header>

    <section class="hero">
      <div class="hero-badge">答辩演示 · 三条角色路径</div>
      <h1>系统演示指南</h1>
      <p>
        按下面的清单走一遍学生、企业和管理员功能。每一步都可以直接打开；未登录时会跳到登录页并自动填入对应账号。
      </p>
    </section>

    <el-row :gutter="16">
      <el-col v-for="role in roles" :key="role.key" :xs="24" :lg="8">
        <el-card shadow="never" class="role-card">
          <template #header>
            <div class="role-head">
              <div>
                <div class="role-title">{{ role.title }}</div>
                <div class="role-account">{{ role.account }}</div>
              </div>
              <el-tag :type="role.tag" effect="plain">{{ role.key }}</el-tag>
            </div>
          </template>

          <ol class="checklist">
            <li v-for="(step, index) in role.steps" :key="step.title">
              <span class="mark">{{ index + 1 }}</span>
              <div class="step-body">
                <div class="step-title">
                  {{ step.title }}
                  <el-tag v-if="step.optional" size="small" type="info">可选</el-tag>
                </div>
                <p class="step-desc">{{ step.desc }}</p>
                <div class="step-actions">
                  <el-button
                    v-for="link in step.links"
                    :key="link.path"
                    link
                    type="primary"
                    @click="openPath(role.key, link.path)"
                  >
                    {{ link.label }}
                  </el-button>
                </div>
              </div>
            </li>
          </ol>

          <el-button class="role-btn" type="primary" plain @click="openPath(role.key, role.entry)">
            {{ roleButtonText(role.key) }}
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { roleHome } from '@/utils/role'

const router = useRouter()
const userStore = useUserStore()

const roles = [
  {
    key: 'student',
    title: '学生',
    account: 'student / student123',
    tag: 'success',
    entry: '/student/dashboard',
    steps: [
      {
        title: '登录后查看求职看板',
        desc: '看投递漏斗、技能雷达和薪资预测。',
        links: [{ label: '打开求职看板', path: '/student/dashboard' }]
      },
      {
        title: '浏览职位并投递',
        desc: '搜索职位，打开详情后选择简历投递。',
        links: [{ label: '去看职位', path: '/student/jobs' }]
      },
      {
        title: '查看为你推荐',
        desc: '根据档案和技能匹配岗位。',
        links: [{ label: '打开推荐', path: '/student/recommend' }]
      },
      {
        title: '向就业助手提问',
        desc: '例如「杭州后端实习薪资」，也可点页面上的示例问题。',
        links: [{ label: '打开就业助手', path: '/student/assistant' }]
      }
    ]
  },
  {
    key: 'company',
    title: '企业',
    account: 'company / company123',
    tag: 'warning',
    entry: '/company/dashboard',
    steps: [
      {
        title: '登录后查看招聘看板',
        desc: '看职位表现、投递状态和候选人技能。',
        links: [{ label: '打开招聘看板', path: '/company/dashboard' }]
      },
      {
        title: '管理职位并推进候选人',
        desc: '发布或编辑职位，再把投递推进到笔试、面试或录用。',
        links: [
          { label: '职位管理', path: '/company/jobs' },
          { label: '候选人', path: '/company/candidates' }
        ]
      },
      {
        title: '使用招聘助手',
        desc: '让助手起草职位说明，或查看已发布职位的候选人。',
        links: [{ label: '打开招聘助手', path: '/company/assistant' }]
      }
    ]
  },
  {
    key: 'admin',
    title: '管理员',
    account: 'admin / admin123',
    tag: 'danger',
    entry: '/admin/analytics',
    steps: [
      {
        title: '登录后查看数据分析',
        desc: '看 Spark 离线结果、推荐评估和 RAG 知识库指标。',
        links: [{ label: '打开数据分析', path: '/admin/analytics' }]
      },
      {
        title: '审核企业与职位',
        desc: '处理企业入驻资质和招聘职位合规。',
        links: [
          { label: '企业审核', path: '/admin/companies' },
          { label: '职位审核', path: '/admin/jobs' }
        ]
      },
      {
        title: '推荐评估、知识库与数据助手',
        desc: '查看推荐指标、维护知识文档，或向数据助手提问。',
        links: [
          { label: '推荐评估', path: '/admin/recommend' },
          { label: '知识库', path: '/admin/knowledge' },
          { label: '数据助手', path: '/admin/assistant' }
        ]
      },
      {
        title: '触发 Spark 分析',
        desc: '在数据分析页点击「运行 Spark 分析」。任务会写入批次记录。',
        optional: true,
        links: [{ label: '去运行分析', path: '/admin/analytics' }]
      }
    ]
  }
]

function roleButtonText(role) {
  if (userStore.isLoggedIn && userStore.roleName === role) {
    return '进入该角色起点'
  }
  return '一键去登录并填账号'
}

function goWorkspace() {
  router.push(roleHome(userStore.roleName))
}

function openPath(role, path) {
  if (userStore.isLoggedIn && userStore.roleName === role) {
    router.push(path)
    return
  }
  if (userStore.isLoggedIn) {
    ElMessage.warning('当前已登录其他角色，请先退出后再使用该演示账号')
    return
  }
  router.push({ path: '/login', query: { demo: role, redirect: path } })
}
</script>

<style scoped>
.demo-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}
.brand {
  font-size: 18px;
  font-weight: 700;
  color: #1a202c;
  cursor: pointer;
  white-space: nowrap;
}
.top-nav,
.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.welcome {
  color: #4a5568;
  font-size: 14px;
}
.hero {
  margin-bottom: 20px;
}
.hero-badge {
  display: inline-block;
  margin-bottom: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 13px;
}
h1 {
  margin: 0 0 8px;
  font-size: 28px;
  color: #1a202c;
}
.hero p {
  margin: 0;
  max-width: 720px;
  color: #4a5568;
  line-height: 1.7;
}
.role-card {
  height: 100%;
  margin-bottom: 16px;
}
.role-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.role-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a202c;
}
.role-account {
  margin-top: 4px;
  color: #718096;
  font-size: 13px;
}
.checklist {
  list-style: none;
  margin: 0;
  padding: 0;
}
.checklist li {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #edf2f7;
}
.checklist li:last-child {
  border-bottom: none;
}
.mark {
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #ecf5ff;
  color: #409eff;
  font-size: 13px;
  font-weight: 700;
  line-height: 24px;
  text-align: center;
}
.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #2d3748;
}
.step-desc {
  margin: 4px 0 0;
  color: #718096;
  font-size: 13px;
  line-height: 1.6;
}
.step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 2px;
}
.role-btn {
  width: 100%;
  margin-top: 8px;
}
@media (max-width: 900px) {
  .top-bar {
    flex-wrap: wrap;
  }
  .top-nav {
    order: 3;
    width: 100%;
  }
}
</style>
