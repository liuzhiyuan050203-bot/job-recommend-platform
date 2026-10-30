<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header><span class="title">我的收藏</span></template>
      <el-empty v-if="!rows.length && !loading" description="还没有收藏职位" />
      <el-card v-for="job in rows" :key="job.id" class="job-card" shadow="hover" @click="open(job)">
        <div class="job-top">
          <div>
            <div class="job-title">{{ job.title }}</div>
            <div class="company">{{ job.companyName || '企业' }} · {{ job.city || '-' }} · {{ job.techDirection || '-' }}</div>
          </div>
          <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}</div>
        </div>
        <div class="meta">
          <el-tag v-if="job.shelfStatus === 0" size="small" type="info">已下架</el-tag>
          <el-tag v-for="name in job.tagNames || []" :key="name" size="small">{{ name }}</el-tag>
          <el-button link type="danger" @click.stop="cancel(job)">取消收藏</el-button>
        </div>
      </el-card>
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
import { ElMessage } from 'element-plus'
import { getFavorites, removeFavorite } from '@/api/student'
import { salaryText } from '@/utils/job'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const page = reactive({ current: 1, size: 10, total: 0 })

async function load() {
  loading.value = true
  try {
    const res = await getFavorites({ current: page.current, size: page.size })
    rows.value = res.records || []
    page.total = res.total || 0
  } finally {
    loading.value = false
  }
}

function open(job) {
  if (job.auditStatus === 1 && job.shelfStatus === 1) {
    router.push(`/student/jobs/${job.id}`)
  }
}

async function cancel(job) {
  await removeFavorite(job.id)
  ElMessage.success('已取消收藏')
  load()
}

onMounted(load)
</script>

<style scoped>
.title { font-weight: 600; }
.job-card { margin-bottom: 12px; cursor: pointer; }
.job-top { display: flex; justify-content: space-between; }
.job-title { font-weight: 600; }
.company { color: var(--el-text-color-secondary); margin-top: 4px; }
.salary { color: #e67e22; font-weight: 600; }
.meta { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; }
</style>
