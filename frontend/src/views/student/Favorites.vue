<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">我的收藏</span>
          <span class="hint">已下架或已删除的职位会保留在列表中，便于你清理</span>
        </div>
      </template>
      <div v-loading="loading">
      <el-empty v-if="!rows.length && !loading" description="还没有收藏职位，在职位详情页点「收藏」即可加入">
        <el-button type="primary" @click="router.push('/student/jobs')">去找职位</el-button>
      </el-empty>
      <el-card v-for="job in rows" :key="job.id" class="job-card" :class="{ offline: !online(job) }" shadow="hover" @click="open(job)">
        <div class="job-top">
          <div>
            <div class="job-title">{{ job.title }}</div>
            <div class="company">{{ job.companyName || '企业' }} · {{ job.city || '-' }} · {{ job.techDirection || '-' }}</div>
          </div>
          <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}<sup v-if="isEstimatedSalary(job)">*</sup></div>
        </div>
        <div class="meta">
          <el-tag v-if="!online(job)" size="small" type="info" effect="dark">已下架</el-tag>
          <el-tag v-for="name in (job.tagNames || []).slice(0, 6)" :key="name" size="small" effect="plain">{{ name }}</el-tag>
          <JobSourceTag :job="job" />
          <span class="spacer" />
          <el-button link type="danger" @click.stop="cancel(job)">取消收藏</el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import JobSourceTag from '@/components/JobSourceTag.vue'
import { getFavorites, removeFavorite } from '@/api/student'
import { isEstimatedSalary, salaryText } from '@/utils/job'

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

function online(job) {
  return job.auditStatus === 1 && job.shelfStatus === 1
}

function open(job) {
  if (online(job)) {
    router.push(`/student/jobs/${job.id}`)
  } else {
    ElMessage.info('该职位已下架或已删除，无法查看详情')
  }
}

async function cancel(job) {
  const ok = await ElMessageBox.confirm(`确定取消收藏「${job.title}」吗？`, '取消收藏', {
    type: 'warning', confirmButtonText: '取消收藏', cancelButtonText: '保留'
  }).then(() => true).catch(() => false)
  if (!ok) return
  try {
    await removeFavorite(job.id)
    ElMessage.success('已取消收藏')
    if (rows.value.length === 1 && page.current > 1) page.current -= 1
    load()
  } catch {
    // 拦截器已提示
  }
}

onMounted(load)
</script>

<style scoped>
.title { font-weight: 600; }
.job-card { margin-bottom: 12px; cursor: pointer; }
.job-top { display: flex; justify-content: space-between; }
.job-title { font-weight: 600; }
.company { color: var(--el-text-color-secondary); margin-top: 4px; }
.salary { color: #e67e22; font-weight: 600; white-space: nowrap; }
.salary sup { color: #e6a23c; }
.spacer { flex: 1; }
.offline { opacity: 0.6; }
.meta { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }

</style>
