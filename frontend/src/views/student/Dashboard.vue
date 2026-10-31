<template>
  <div class="page-container">
    <el-skeleton :loading="loading" animated>
      <template #template>
        <el-skeleton-item variant="rect" style="height: 320px" />
      </template>
      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <el-card shadow="never">
            <template #header><span class="title">投递状态</span></template>
            <el-empty v-if="!statusTotal" description="还没有投递记录" />
            <EChart v-else :option="statusOption" height="320px" />
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="never">
            <template #header><span class="title">技能雷达</span></template>
            <el-empty v-if="!radarSkills.length" description="完善技能或等待推荐后展示对比" />
            <EChart v-else :option="radarOption" height="320px" />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="10">
          <el-card shadow="never">
            <template #header><span class="title">薪资预测</span></template>
            <p v-if="!canPredict" class="hint">
              请先在个人档案中填写期望城市、技术方向和学历。
              <el-button link type="primary" @click="router.push('/student/profile')">去完善</el-button>
            </p>
            <el-skeleton v-else-if="predictLoading" animated :rows="2" />
            <div v-else-if="predict" class="predict">
              <div class="predict-salary">{{ formatYuan(predict.predictedSalary) }}</div>
              <div class="hint">
                区间 {{ formatYuan(predict.ciLow) }} ~ {{ formatYuan(predict.ciHigh) }}
              </div>
              <div class="hint">
                {{ predict.city }} · {{ predict.techDirection }} · {{ educationName }} · {{ yearsText }}
              </div>
            </div>
            <p v-else class="hint">暂时无法得到预测结果，请稍后重试。</p>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="14">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span class="title">推荐摘要</span>
                <el-button link type="primary" @click="router.push('/student/recommend')">查看全部</el-button>
              </div>
            </template>
            <el-empty v-if="!recommends.length" description="完成档案和技能后会生成推荐" />
            <div
              v-for="job in recommends"
              :key="job.positionId"
              class="job"
              @click="router.push(`/student/jobs/${job.positionId}`)"
            >
              <div class="job-title">{{ job.title }}</div>
              <div class="job-meta">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
              <div class="job-meta">{{ salaryText(job.salaryMin, job.salaryMax) }} · 匹配 {{ formatScore(job.matchScore) }}</div>
              <div v-if="job.reason" class="job-reason">{{ job.reason }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-skeleton>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import EChart from '@/components/EChart.vue'
import { predictSalary } from '@/api/public'
import { getStudentDashboard } from '@/api/student'
import { salaryText } from '@/utils/job'

const EDUCATION = { 1: '专科', 2: '本科', 3: '硕士', 4: '博士' }

const router = useRouter()
const loading = ref(true)
const predictLoading = ref(false)
const board = ref({
  applicationStatus: [],
  skillRadar: { skills: [], myLevels: [], jobAvgLevels: [] },
  profile: {},
  recommendTop: []
})
const predict = ref(null)

const statusRows = computed(() => board.value.applicationStatus || [])
const statusTotal = computed(() => statusRows.value.reduce((sum, item) => sum + Number(item.count || 0), 0))
const radarSkills = computed(() => board.value.skillRadar?.skills || [])
const recommends = computed(() => board.value.recommendTop || [])
const profile = computed(() => board.value.profile || {})

const canPredict = computed(() => {
  const data = profile.value
  const education = Number(data.education)
  return Boolean(data.city && data.techDirection && education >= 1 && education <= 4)
})

const educationName = computed(() => EDUCATION[Number(profile.value.education)] || '-')
const yearsText = computed(() => {
  const years = Number(profile.value.experienceYears)
  if (!Number.isFinite(years)) return '应届'
  return years <= 0 ? '应届' : `${years} 年经验`
})

const statusOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [
    {
      name: '投递状态',
      type: 'pie',
      radius: ['42%', '68%'],
      data: statusRows.value
        .filter((item) => Number(item.count) > 0)
        .map((item) => ({ name: item.label, value: Number(item.count) }))
    }
  ]
}))

const radarOption = computed(() => {
  const radar = board.value.skillRadar || {}
  const skills = radar.skills || []
  return {
    tooltip: {},
    legend: { bottom: 0, data: ['我的熟练度', '职位相关平均熟练度'] },
    radar: {
      indicator: skills.map((name) => ({ name, max: 5 })),
      radius: '62%'
    },
    series: [
      {
        type: 'radar',
        data: [
          { name: '我的熟练度', value: radar.myLevels || [] },
          { name: '职位相关平均熟练度', value: radar.jobAvgLevels || [] }
        ]
      }
    ]
  }
})

function formatYuan(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${Math.round(number).toLocaleString('zh-CN')} 元/月`
}

function formatScore(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(1) : '-'
}

function skillParam(skills) {
  let text = ''
  for (const name of skills || []) {
    if (!name) continue
    const next = text ? `${text},${name}` : name
    if (next.length > 200) break
    text = next
  }
  return text
}

async function loadPredict() {
  if (!canPredict.value) {
    predict.value = null
    return
  }
  predictLoading.value = true
  try {
    const data = profile.value
    predict.value = await predictSalary({
      city: data.city,
      techDirection: data.techDirection,
      education: data.education,
      experienceYears: data.experienceYears ?? 0,
      skills: skillParam(data.skills)
    })
  } catch {
    predict.value = null
  } finally {
    predictLoading.value = false
  }
}

onMounted(async () => {
  try {
    board.value = (await getStudentDashboard()) || board.value
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
  await loadPredict()
})
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hint {
  color: #606266;
  line-height: 1.7;
}
.predict-salary {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 8px;
}
.job {
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
}
.job:last-child {
  border-bottom: none;
}
.job-title {
  font-weight: 600;
}
.job-meta,
.job-reason {
  margin-top: 4px;
  color: #909399;
  font-size: 13px;
}
</style>
