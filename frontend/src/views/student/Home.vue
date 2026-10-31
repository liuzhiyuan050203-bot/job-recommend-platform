<template>
  <div v-loading="loading" class="page-container">
    <el-card shadow="never">
      <template #header><span class="title">学生首页</span></template>
      <h3>未来 7 天的笔试 / 面试</h3>
      <el-empty v-if="!loading && !upcoming.length" description="近期没有待进行的安排" />
      <el-card v-for="item in upcoming" :key="item.id" class="item" shadow="never">
        <div class="line">
          <b>{{ item.interviewTime }}</b>
          <span>{{ item.roundName }}</span>
          <span>{{ item.jobTitle }}</span>
          <span>{{ item.companyName }}</span>
        </div>
        <div class="sub">{{ item.interviewTypeName }} · {{ item.interviewType === 1 ? (item.meetingUrl || '链接待定') : (item.location || '地点待定') }}</div>
      </el-card>
      <div class="links">
        <el-button type="primary" @click="router.push('/student/jobs')">去搜职位</el-button>
        <el-button @click="router.push('/student/applications')">我的投递</el-button>
        <el-button @click="router.push('/student/resume')">维护简历</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="latest">
      <template #header>
        <div class="card-header">
          <span class="title">为你推荐</span>
          <el-button link type="primary" @click="router.push('/student/recommend')">查看全部</el-button>
        </div>
      </template>
      <el-empty v-if="!loading && !recommends.length" description="完成档案和技能后会生成推荐" />
      <div v-for="job in recommends" :key="job.positionId" class="job" @click="router.push(`/student/jobs/${job.positionId}`)">
        <span>{{ job.title }}</span>
        <span>{{ job.companyName }} · {{ job.city }}</span>
        <span class="salary">匹配 {{ formatScore(job.matchScore) }}</span>
      </div>
    </el-card>

    <el-card shadow="never" class="latest">
      <template #header><span class="title">最新职位</span></template>
      <el-empty v-if="!loading && !jobs.length" description="暂时没有可浏览的职位" />
      <div v-for="job in jobs" :key="job.id" class="job" @click="router.push(`/student/jobs/${job.id}`)">
        <span>{{ job.title }}</span>
        <span>{{ job.companyName }} · {{ job.city }}</span>
        <span class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchJobs } from '@/api/public'
import { getRecommendations, getUpcomingInterviews } from '@/api/student'
import { salaryText } from '@/utils/job'

const router = useRouter()
const loading = ref(true)
const upcoming = ref([])
const jobs = ref([])
const recommends = ref([])

function formatScore(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(1) : '-'
}

onMounted(async () => {
  try {
    const [upcomingRes, jobsRes, recommendRes] = await Promise.allSettled([
      getUpcomingInterviews(),
      searchJobs({ current: 1, size: 5, sort: 'newest' }),
      getRecommendations({ current: 1, size: 4 })
    ])
    upcoming.value = upcomingRes.status === 'fulfilled' ? (upcomingRes.value || []) : []
    jobs.value = jobsRes.status === 'fulfilled' ? (jobsRes.value?.records || []) : []
    recommends.value = recommendRes.status === 'fulfilled' ? (recommendRes.value?.records || []) : []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.title { font-weight: 600; }
.item { margin-bottom: 8px; }
.line { display: flex; gap: 12px; flex-wrap: wrap; }
.sub { color: var(--el-text-color-secondary); margin-top: 4px; }
.links { display: flex; gap: 8px; margin-top: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.latest { margin-top: 16px; }
.job { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); cursor: pointer; }
.salary { color: #e67e22; }
</style>
