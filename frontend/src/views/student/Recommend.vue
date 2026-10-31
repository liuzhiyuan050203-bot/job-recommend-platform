<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">为你推荐</span>
          <span class="hint">结合技能、求职意向和相似同学的投递</span>
        </div>
      </template>
      <div v-loading="loading">
        <el-empty v-if="!rows.length && !loading" description="暂时没有合适的职位，先去完善技能或浏览职位" />
        <el-card v-for="job in rows" :key="job.positionId" class="job-card" shadow="hover" @click="open(job)">
          <div class="job-top">
            <div>
              <div class="job-title">{{ job.title }}</div>
              <div class="company">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
            </div>
            <div class="score">匹配 {{ formatScore(job.matchScore) }}</div>
          </div>
          <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}</div>
          <div class="meta">
            <el-tag size="small">{{ labelOf(EDUCATION, job.education) }}</el-tag>
            <el-tag v-for="name in job.tagNames || []" :key="name" size="small" type="success">{{ name }}</el-tag>
            <el-tag v-for="(part, index) in reasonParts(job.reason)" :key="index" size="small" type="warning">{{ part }}</el-tag>
          </div>
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
import { EDUCATION, labelOf, salaryText } from '@/utils/job'

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
.pager { display: flex; justify-content: flex-end; margin-top: 8px; }
</style>
