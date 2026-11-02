<template>
  <div v-loading="loading" class="page-container">
    <el-page-header content="职位详情" @back="router.push('/student/jobs')" />
    <el-card v-if="job" class="detail" shadow="never">
      <div class="head">
        <div>
          <h2>{{ job.title }}</h2>
          <p>{{ job.companyName }} · {{ job.province }} {{ job.city }} {{ job.district }} · {{ job.techDirection }}</p>
        </div>
        <div class="salary-block">
          <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}<sup v-if="job.salaryEstimated" class="estimate-mark">*</sup></div>
          <el-tooltip v-if="job.salaryEstimated" :content="job.salaryNote || ESTIMATE_NOTE" placement="bottom">
            <el-tag size="small" type="warning" effect="plain" class="estimate-tag">估算薪资</el-tag>
          </el-tooltip>
        </div>
      </div>
      <div class="source-line">
        <el-tag v-if="source" size="small" :type="source.type === 'CRAWLER' ? 'info' : 'success'" effect="plain" class="source-badge">
          数据来源：{{ source.label }}
        </el-tag>
        <span v-if="source && source.type === 'CRAWLER'" class="source-meta">
          <template v-if="source.site">{{ source.site }}</template>
          <template v-if="source.project"> · {{ source.project }}</template>
          <template v-if="source.workCities"> · 工作城市 {{ source.workCities }}</template>
          <template v-if="crawledText"> · 抓取于 {{ crawledText }}</template>
        </span>
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
        <el-button v-if="source && source.applyUrl" tag="a" :href="source.applyUrl" target="_blank" rel="noopener noreferrer">
          前往官网查看/投递
        </el-button>
      </div>
      <h3>岗位职责</h3>
      <ol v-if="descriptionItems.length > 1" class="items">
        <li v-for="(item, idx) in descriptionItems" :key="idx">{{ item }}</li>
      </ol>
      <p v-else-if="descriptionItems.length === 1" class="text">{{ descriptionItems[0] }}</p>
      <p v-else class="muted">{{ isCrawled ? '官网接口未提供职责全文，请以官网页面为准。' : '暂无' }}</p>
      <h3>任职要求</h3>
      <ol v-if="requirementItems.length > 1" class="items">
        <li v-for="(item, idx) in requirementItems" :key="idx">{{ item }}</li>
      </ol>
      <p v-else-if="requirementItems.length === 1" class="text">{{ requirementItems[0] }}</p>
      <p v-else class="muted">
        {{ isCrawled ? '官网接口未提供任职要求全文，可先参考上方技能标签，详细要求以官网页面为准。' : '暂无' }}
      </p>
      <h3>福利与地址</h3>
      <p class="text">{{ job.welfare || '暂无' }}</p>
      <p class="text">{{ job.address || '地址待定' }}</p>
      <p v-if="job.salaryEstimated" class="footnote">* 估算薪资：{{ job.salaryNote || ESTIMATE_NOTE }}</p>
    </el-card>

    <el-card shadow="never" class="similar">
      <template #header><span class="title">相似职位</span></template>
      <el-empty v-if="!similar.length" description="暂无相似职位" />
      <div v-for="item in similar" :key="item.id" class="similar-item" @click="openSimilar(item)">
        <div>
          <div class="job-title">{{ item.title }}</div>
          <div class="sub">{{ item.companyName }} · {{ item.city }} · {{ item.techDirection }}</div>
        </div>
        <div class="salary">{{ salaryText(item.salaryMin, item.salaryMax, item.salaryMonths) }}</div>
      </div>
    </el-card>

    <el-dialog v-model="applyVisible" title="确认投递简历" width="560px">
      <el-form label-width="96px">
        <el-form-item label="选择简历" required>
          <el-select v-model="resumeId" filterable placeholder="搜索或选择要投递的在线简历" style="width: 100%">
            <el-option
              v-for="item in applyResumes"
              :key="item.id"
              :label="item.isDefault === 1 ? `${item.title}（默认）` : item.title"
              :value="item.id"
            >
              <span>{{ item.title }}</span>
              <el-tag v-if="item.isDefault === 1" size="small" type="success" style="margin-left: 8px">默认</el-tag>
              <el-tag v-if="(item.title || '').includes('校招')" size="small" type="info" effect="plain" style="margin-left: 6px">校招</el-tag>
            </el-option>
          </el-select>
          <div v-if="!applyResumes.length" class="apply-tip">暂无可用简历（测试简历已隐藏），请先到「在线简历」新建一份。</div>
        </el-form-item>
        <el-form-item label="附带技能">
          <div class="skill-preview">
            <div class="apply-tip">
              已合并个人档案技能与所选简历技能概述，共 {{ previewSkills.length }} 项；绿色表示命中本职位技能标签。
            </div>
            <div v-if="previewSkills.length" class="skill-wrap">
              <el-tag
                v-for="sk in previewSkills"
                :key="sk.name"
                size="small"
                :type="sk.matched ? 'success' : 'info'"
                :effect="sk.matched ? 'light' : 'plain'"
                class="skill-tag"
              >
                <span v-if="sk.matched">✓ </span>{{ sk.name }}
                <span v-if="sk.proficiencyName" class="lvl"> · {{ sk.proficiencyName }}</span>
              </el-tag>
            </div>
            <div v-else class="apply-tip">暂无技能。可在「个人档案」上传 PDF 解析并合并，或在简历技能概述中填写。</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!resumeId" @click="submitApply">确认投递</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getJob, getSimilarJobs } from '@/api/public'
import { addFavorite, applyJob, getResumes, getStudentSkills, removeFavorite } from '@/api/student'
import { EDUCATION, EXPERIENCE, JOB_TYPE, labelOf, salaryText } from '@/utils/job'
import { parseJobText } from '@/utils/jobText'
import { preferredApplyResume, pickApplyResumes, mergePreviewSkills } from '@/utils/resumePick'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const job = ref(null)
const similar = ref([])
const resumes = ref([])
const mySkills = ref([])
const resumeId = ref(null)
const applyVisible = ref(false)
const applyResumes = computed(() => pickApplyResumes(resumes.value))
const previewSkills = computed(() => {
  const selected = applyResumes.value.find((r) => r.id === resumeId.value)
  return mergePreviewSkills(mySkills.value, selected?.skillDesc, job.value?.tagNames)
})

const ESTIMATE_NOTE = '官网未公布薪资，此处薪资为平台按技术方向与城市估算，仅供参考，以官网为准。'
// 后端详情给出整理好的条目；字段缺失时前端再兜底解析一次，不直接插值原始字符串
const descriptionItems = computed(() => (Array.isArray(job.value?.descriptionItems)
  ? job.value.descriptionItems : parseJobText(job.value?.description)))
const requirementItems = computed(() => (Array.isArray(job.value?.requirementItems)
  ? job.value.requirementItems : parseJobText(job.value?.requirement)))
const source = computed(() => job.value?.dataSource || null)
const isCrawled = computed(() => source.value?.type === 'CRAWLER')
const crawledText = computed(() => {
  const raw = source.value?.crawledAt
  return raw ? String(raw).replace('T', ' ').slice(0, 16) : ''
})

async function load() {
  loading.value = true
  try {
    job.value = await getJob(route.params.id)
    try {
      const list = await getSimilarJobs(route.params.id, 6)
      similar.value = Array.isArray(list) ? list : []
    } catch {
      similar.value = []
    }
  } finally {
    loading.value = false
  }
}

function openSimilar(item) {
  router.push(`/student/jobs/${item.id}`)
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
  const [list, skills] = await Promise.all([getResumes(), getStudentSkills().catch(() => [])])
  resumes.value = list || []
  mySkills.value = skills || []
  if (!applyResumes.value.length) {
    ElMessage.warning('请先创建一份正式在线简历（测试简历不会出现在投递列表）')
    router.push('/student/resume')
    return
  }
  const preferred = preferredApplyResume(resumes.value)
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
watch(() => route.params.id, () => {
  load()
})
</script>

<style scoped>
.detail { margin-top: 16px; }
.head { display: flex; justify-content: space-between; gap: 16px; }
.salary { color: #e67e22; font-size: 20px; font-weight: 700; }
.meta { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.stat { color: var(--el-text-color-secondary); }
.actions { display: flex; gap: 8px; margin-bottom: 12px; }
.text { white-space: pre-wrap; line-height: 1.7; }
.items { margin: 0; padding-left: 22px; line-height: 1.8; }
.muted { color: var(--el-text-color-secondary); line-height: 1.7; }
.salary-block { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.estimate-mark { color: #e67e22; font-size: 14px; margin-left: 2px; }
.estimate-tag { cursor: help; }
.source-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
.source-meta { color: var(--el-text-color-secondary); font-size: 12px; }
.footnote { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 16px; border-top: 1px dashed var(--el-border-color); padding-top: 8px; }
.similar { margin-top: 16px; }
.title { font-weight: 600; }
.similar-item { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); cursor: pointer; }
.job-title { font-weight: 600; }
.sub { color: var(--el-text-color-secondary); margin-top: 4px; }
.apply-tip { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.skill-preview { width: 100%; }
.skill-wrap { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.skill-tag .lvl { opacity: 0.75; }
</style>
