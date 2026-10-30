<template>
  <div v-loading="loading" class="page-container">
    <el-page-header content="职位详情" @back="router.push('/student/jobs')" />
    <el-card v-if="job" class="detail" shadow="never">
      <div class="head">
        <div>
          <h2>{{ job.title }}</h2>
          <p>{{ job.companyName }} · {{ job.province }} {{ job.city }} {{ job.district }} · {{ job.techDirection }}</p>
        </div>
        <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}</div>
      </div>
      <div class="meta">
        <el-tag>{{ labelOf(EDUCATION, job.education) }}</el-tag>
        <el-tag type="info">{{ labelOf(EXPERIENCE, job.experienceReq) }}</el-tag>
        <el-tag type="success">{{ labelOf(JOB_TYPE, job.jobType) }}</el-tag>
        <el-tag v-for="name in job.tagNames || []" :key="name">{{ name }}</el-tag>
      </div>
      <p class="stat">招聘 {{ job.headcount }} 人 · 浏览 {{ job.viewCount || 0 }} · 收藏 {{ job.favoriteCount || 0 }} · 投递 {{ job.applyCount || 0 }}</p>
      <div class="actions">
        <el-button :type="job.favorited ? 'warning' : 'default'" @click="toggleFavorite">
          {{ job.favorited ? '已收藏' : '收藏' }}
        </el-button>
        <el-button type="primary" :disabled="job.applied" @click="openApply">
          {{ job.applied ? '已投递' : '投递简历' }}
        </el-button>
      </div>
      <h3>岗位职责</h3>
      <p class="text">{{ job.description || '暂无' }}</p>
      <h3>任职要求</h3>
      <p class="text">{{ job.requirement || '暂无' }}</p>
      <h3>福利与地址</h3>
      <p class="text">{{ job.welfare || '暂无' }}</p>
      <p class="text">{{ job.address || '地址待定' }}</p>
    </el-card>

    <el-dialog v-model="applyVisible" title="选择简历投递" width="420px">
      <el-select v-model="resumeId" placeholder="选择简历" style="width: 100%">
        <el-option v-for="item in resumes" :key="item.id" :label="item.isDefault === 1 ? `${item.title}（默认）` : item.title" :value="item.id" />
      </el-select>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitApply">确认投递</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getJob } from '@/api/public'
import { addFavorite, applyJob, getResumes, removeFavorite } from '@/api/student'
import { EDUCATION, EXPERIENCE, JOB_TYPE, labelOf, salaryText } from '@/utils/job'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const job = ref(null)
const resumes = ref([])
const resumeId = ref(null)
const applyVisible = ref(false)

async function load() {
  loading.value = true
  try {
    job.value = await getJob(route.params.id)
  } finally {
    loading.value = false
  }
}

async function toggleFavorite() {
  if (!job.value) return
  if (job.value.favorited) {
    await removeFavorite(job.value.id)
    ElMessage.success('已取消收藏')
  } else {
    await addFavorite(job.value.id)
    ElMessage.success('已收藏')
  }
  await load()
}

async function openApply() {
  resumes.value = await getResumes()
  if (!resumes.value.length) {
    ElMessage.warning('请先创建在线简历')
    router.push('/student/resume')
    return
  }
  const preferred = resumes.value.find((item) => item.isDefault === 1) || resumes.value[0]
  resumeId.value = preferred.id
  applyVisible.value = true
}

async function submitApply() {
  if (!resumeId.value) {
    ElMessage.warning('请选择简历')
    return
  }
  saving.value = true
  try {
    await applyJob({ jobId: job.value.id, resumeId: resumeId.value })
    ElMessage.success('投递成功')
    applyVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.detail { margin-top: 16px; }
.head { display: flex; justify-content: space-between; gap: 16px; }
.salary { color: #e67e22; font-size: 20px; font-weight: 700; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.stat { color: var(--el-text-color-secondary); }
.actions { display: flex; gap: 8px; margin-bottom: 12px; }
.text { white-space: pre-wrap; line-height: 1.7; }
</style>
