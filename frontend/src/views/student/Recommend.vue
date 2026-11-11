<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">为你推荐</span>
          <span class="hint">综合你的技能、求职意向和相似同学的投递行为排序；已投递的职位不再出现</span>
        </div>
      </template>
      <div v-loading="loading">
        <el-empty v-if="!rows.length && !loading" description="暂时没有推荐。完善期望方向、城市和技能后，推荐会更准确">
          <el-button type="primary" @click="router.push('/student/profile')">完善档案与技能</el-button>
          <el-button @click="router.push('/student/jobs')">浏览全部职位</el-button>
        </el-empty>
        <el-card v-for="job in rows" :key="job.positionId" class="job-card" shadow="hover" @click="open(job)">
          <div class="job-top">
            <div>
              <div class="job-title">{{ job.title }}</div>
              <div class="company">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
            </div>
            <el-tooltip content="综合匹配度（0-100），由技能重合、方向/城市匹配与协同过滤分融合得到" placement="top">
              <div class="score">匹配 {{ formatScore(job.matchScore) }}</div>
            </el-tooltip>
          </div>
          <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}<sup v-if="isEstimatedSalary(job)">*</sup></div>
          <div class="meta">
            <el-tag size="small">{{ labelOf(EDUCATION, job.education) }}</el-tag>
            <el-tag v-for="name in (job.tagNames || []).slice(0, 6)" :key="name" size="small" type="success" effect="plain">{{ name }}</el-tag>
            <JobSourceTag :job="job" />
          </div>
          <ul v-if="reasonParts(job.reason).length" class="reasons">
            <li v-for="(part, index) in reasonParts(job.reason)" :key="index">{{ part }}</li>
          </ul>
        </el-card>
      </div>
      <div class="pager">
        <el-pagination
          v-model:current-page="page.current"
          v-model:page-size="page.size"
          :total="page.total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getRecommendations } from '@/api/student'
import { EDUCATION, isEstimatedSalary, labelOf, salaryText } from '@/utils/job'
import JobSourceTag from '@/components/JobSourceTag.vue'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const page = reactive({ current: 1, size: 10, total: 0 })

function formatScore(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(1) : '-'
}

function reasonParts(reason) {
  if (!reason) return []
  return String(reason).split('；').map((item) => item.trim()).filter(Boolean)
}

function open(job) {
  router.push(`/student/jobs/${job.positionId}`)
}

async function load() {
  loading.value = true
  try {
    const data = await getRecommendations({ current: page.current, size: page.size })
    rows.value = data?.records || []
    page.total = Number(data?.total || 0)
  } catch {
    rows.value = []
    page.total = 0
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-container { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.title { font-weight: 600; font-size: 16px; }
.hint { color: var(--el-text-color-secondary); font-size: 13px; }
.job-card { margin-bottom: 12px; cursor: pointer; }
.job-top { display: flex; justify-content: space-between; gap: 12px; }
.job-title { font-size: 16px; font-weight: 600; }
.company { margin-top: 4px; color: var(--el-text-color-secondary); }
.score { color: #409eff; font-weight: 700; white-space: nowrap; }
.salary { margin: 8px 0; color: #e67e22; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; }
.salary sup { color: #e6a23c; }
.reasons { margin: 8px 0 0; padding-left: 18px; color: var(--el-text-color-regular); font-size: 13px; line-height: 1.7; }
</style>
