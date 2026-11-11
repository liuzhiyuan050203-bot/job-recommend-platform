<template>
  <div v-loading="loading" class="page-container">
    <el-card shadow="never" class="welcome">
      <div class="welcome-row">
        <div>
          <div class="hello">你好，{{ userStore.nickname }} 👋</div>
          <div class="sub">
            <template v-if="profile && (profile.expectDirection || profile.expectCity)">
              求职意向：{{ profile.expectDirection || '方向未填' }} · {{ profile.expectCity || '城市未填' }}
              <template v-if="profile.expectSalaryMin"> · 期望 {{ salaryText(profile.expectSalaryMin, profile.expectSalaryMax) }}</template>
            </template>
            <template v-else>先完善求职意向，推荐会更准确</template>
          </div>
        </div>
        <div class="completeness">
          <el-progress type="circle" :percentage="completeness" :width="72" :stroke-width="7" :status="completeness >= 100 ? 'success' : ''" />
          <div class="todo">
            <div class="todo-title">求职材料完整度</div>
            <div v-if="!todos.length" class="todo-done">材料齐全，可以放心投递</div>
            <el-button v-for="t in todos" :key="t.text" link type="primary" size="small" @click="router.push(t.path)">· {{ t.text }}</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col v-for="tile in tiles" :key="tile.label" :xs="12" :sm="6">
        <el-card shadow="never" class="stat-tile clickable" @click="router.push(tile.path)">
          <div class="stat-label">{{ tile.label }}</div>
          <div class="stat-value">{{ tile.value }}</div>
          <div class="stat-sub">{{ tile.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">常用功能</span></template>
      <div class="shortcuts">
        <div v-for="s in shortcuts" :key="s.path" class="shortcut" @click="router.push(s.path)">
          <el-icon :size="22" :color="s.color"><component :is="s.icon" /></el-icon>
          <div class="shortcut-text">
            <div class="shortcut-title">{{ s.title }}</div>
            <div class="shortcut-desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="fill">
          <template #header>
            <div class="card-header">
              <span class="title">未来 7 天的笔试 / 面试</span>
              <el-button link type="primary" @click="router.push('/student/applications')">投递进度</el-button>
            </div>
          </template>
          <el-empty v-if="!loading && !upcoming.length" :image-size="70" description="近期没有待进行的安排" />
          <div v-for="item in upcoming" :key="item.id" class="list-row">
            <div>
              <div class="row-title">{{ item.roundName }} · {{ item.jobTitle }}</div>
              <div class="row-sub">
                {{ item.companyName }} · {{ item.interviewTypeName }} ·
                <a v-if="item.interviewType === 1 && isUrl(item.meetingUrl)" :href="item.meetingUrl" target="_blank" rel="noopener noreferrer">进入会议</a>
                <span v-else>{{ item.interviewType === 1 ? (item.meetingUrl || '链接待定') : (item.location || '地点待定') }}</span>
              </div>
            </div>
            <el-tag type="warning" effect="plain">{{ item.interviewTime }}</el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="fill">
          <template #header>
            <div class="card-header">
              <span class="title">为你推荐</span>
              <el-button link type="primary" @click="router.push('/student/recommend')">查看全部</el-button>
            </div>
          </template>
          <el-empty v-if="!loading && !recommends.length" :image-size="70" description="完善档案和技能后会生成推荐" />
          <div v-for="job in recommends" :key="job.positionId" class="list-row clickable" @click="router.push(`/student/jobs/${job.positionId}`)">
            <div>
              <div class="row-title">{{ job.title }}</div>
              <div class="row-sub">{{ job.companyName }} · {{ job.city }} · {{ salaryText(job.salaryMin, job.salaryMax) }}<sup v-if="isEstimatedSalary(job)">*</sup></div>
            </div>
            <span class="score">匹配 {{ formatScore(job.matchScore) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">最新职位</span>
          <el-button link type="primary" @click="router.push('/student/jobs')">更多职位</el-button>
        </div>
      </template>
      <el-empty v-if="!loading && !jobs.length" :image-size="70" description="暂时没有可浏览的职位" />
      <div v-for="job in jobs" :key="job.id" class="list-row clickable" @click="router.push(`/student/jobs/${job.id}`)">
        <div>
          <div class="row-title">{{ job.title }} <JobSourceTag :job="job" :show-estimate="false" /></div>
          <div class="row-sub">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
        </div>
        <span class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}<sup v-if="isEstimatedSalary(job)">*</sup></span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchJobs } from '@/api/public'
import {
  getApplications, getFavorites, getRecommendations, getResumes, getStudentProfile, getStudentSkills, getUpcomingInterviews
} from '@/api/student'
import { useUserStore } from '@/stores/user'
import JobSourceTag from '@/components/JobSourceTag.vue'
import { isEstimatedSalary, salaryText } from '@/utils/job'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)
const upcoming = ref([])
const jobs = ref([])
const recommends = ref([])
const profile = ref(null)
const skills = ref([])
const resumes = ref([])
const appTotal = ref(0)
const appActive = ref(0)
const appOffer = ref(0)
const favTotal = ref(0)

const shortcuts = [
  { title: '职位搜索', desc: '按方向、城市、薪资筛选', path: '/student/jobs', icon: 'Search', color: '#409eff' },
  { title: '为你推荐', desc: '技能 + 协同过滤推荐', path: '/student/recommend', icon: 'MagicStick', color: '#e6a23c' },
  { title: '薪资预测', desc: '估算目标岗位月薪', path: '/student/salary', icon: 'Money', color: '#67c23a' },
  { title: '就业助手', desc: '政策、岗位、技能问答', path: '/student/assistant', icon: 'ChatLineRound', color: '#8e44ad' },
  { title: '在线简历', desc: '维护投递用的简历', path: '/student/resume', icon: 'Document', color: '#909399' },
  { title: '上传 PDF 识别技能', desc: '自动补全技能档案', path: '/student/profile', icon: 'Upload', color: '#f56c6c' }
]

const tiles = computed(() => [
  { label: '累计投递', value: appTotal.value, sub: '查看全部投递', path: '/student/applications' },
  { label: '流程中', value: appActive.value, sub: '笔试 / 面试阶段', path: '/student/applications' },
  { label: '已录用', value: appOffer.value, sub: appOffer.value ? '恭喜拿到 offer' : '继续加油', path: '/student/applications' },
  { label: '收藏职位', value: favTotal.value, sub: '稍后再投', path: '/student/favorites' }
])

const todos = computed(() => {
  const list = []
  const p = profile.value || {}
  if (!p.school || !p.major) list.push({ text: '补全学校与专业', path: '/student/profile' })
  if (!p.expectDirection || !p.expectCity) list.push({ text: '填写期望方向和城市', path: '/student/profile' })
  if (skills.value.length < 3) list.push({ text: `添加技能（当前 ${skills.value.length} 项，建议 ≥3）`, path: '/student/profile' })
  if (!resumes.value.length) list.push({ text: '创建一份在线简历', path: '/student/resume' })
  return list
})
const completeness = computed(() => Math.round(((4 - todos.value.length) / 4) * 100))

function formatScore(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(1) : '-'
}

function isUrl(v) {
  return /^https?:\/\//i.test(v || '')
}

onMounted(async () => {
  const pick = (r, fallback) => (r.status === 'fulfilled' ? r.value : fallback)
  try {
    const res = await Promise.allSettled([
      getUpcomingInterviews(),
      searchJobs({ current: 1, size: 5, sort: 'newest', source: 'internal' }),
      getRecommendations({ current: 1, size: 4 }),
      getStudentProfile(),
      getStudentSkills(),
      getResumes(),
      getApplications({ current: 1, size: 1 }),
      getApplications({ current: 1, size: 1, status: 1 }),
      getApplications({ current: 1, size: 1, status: 2 }),
      getApplications({ current: 1, size: 1, status: 3 }),
      getFavorites({ current: 1, size: 1 })
    ])
    upcoming.value = pick(res[0], []) || []
    jobs.value = pick(res[1], {})?.records || []
    recommends.value = pick(res[2], {})?.records || []
    profile.value = pick(res[3], null)
    skills.value = pick(res[4], []) || []
    resumes.value = pick(res[5], []) || []
    appTotal.value = pick(res[6], {})?.total || 0
    appActive.value = (pick(res[7], {})?.total || 0) + (pick(res[8], {})?.total || 0)
    appOffer.value = pick(res[9], {})?.total || 0
    favTotal.value = pick(res[10], {})?.total || 0
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.title { font-weight: 600; }
.welcome-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.hello { font-size: 20px; font-weight: 600; color: #1a202c; }
.sub { color: var(--el-text-color-secondary); margin-top: 6px; }
.completeness { display: flex; align-items: center; gap: 12px; }
.todo { display: flex; flex-direction: column; align-items: flex-start; }
.todo-title { font-size: 13px; color: var(--el-text-color-regular); margin-bottom: 2px; }
.todo-done { font-size: 12px; color: #67c23a; }
.todo :deep(.el-button + .el-button) { margin-left: 0; }
.shortcuts { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.shortcut { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; cursor: pointer; transition: all 0.15s; }
.shortcut:hover { border-color: var(--el-color-primary-light-5); background: #f8fbff; }
.shortcut-title { font-weight: 600; font-size: 14px; }
.shortcut-desc { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 2px; }
.fill { height: 100%; }
.list-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.list-row:last-child { border-bottom: none; }
.list-row.clickable { cursor: pointer; }
.list-row.clickable:hover .row-title { color: var(--el-color-primary); }
.row-title { font-weight: 500; }
.row-sub { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 4px; }
.row-sub sup, .salary sup { color: #e6a23c; }
.salary { color: #e67e22; white-space: nowrap; }
.score { color: #409eff; font-weight: 600; white-space: nowrap; }
.el-row { row-gap: 16px; }
</style>
