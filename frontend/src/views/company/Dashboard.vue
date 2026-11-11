<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col v-for="t in tiles" :key="t.label" :xs="12" :sm="6">
        <el-card shadow="never" class="stat-tile clickable" :class="{ urgent: t.urgent && t.value > 0 }" @click="router.push(t.path)">
          <div class="stat-label">{{ t.label }}</div>
          <div class="stat-value">{{ t.value }}</div>
          <div class="stat-sub">{{ t.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">快捷操作</span></template>
      <div class="shortcuts">
        <el-button type="primary" icon="Plus" @click="router.push({ path: '/company/jobs', query: { create: '1' } })">发布新职位</el-button>
        <el-button icon="User" @click="router.push({ path: '/company/candidates', query: { status: 0 } })">筛选新投递</el-button>
        <el-button icon="Calendar" @click="router.push('/company/interviews')">查看面试安排</el-button>
        <el-button icon="ChatLineRound" @click="router.push('/company/assistant')">让助手写 JD</el-button>
        <el-button icon="OfficeBuilding" @click="router.push('/company/profile')">维护企业资料</el-button>
      </div>
    </el-card>

    <el-skeleton :loading="loading" animated>
      <template #template>
        <el-skeleton-item variant="rect" style="height: 320px" />
      </template>
      <el-card shadow="never">
        <template #header><span class="title">职位表现</span></template>
        <el-empty v-if="!jobs.length" description="还没有发布职位">
          <el-button type="primary" @click="router.push({ path: '/company/jobs', query: { create: '1' } })">发布第一个职位</el-button>
        </el-empty>
        <template v-else>
          <EChart :option="jobOption" height="360px" />
          <el-table :data="jobs" size="small" class="table">
            <el-table-column prop="title" label="职位" min-width="180" />
            <el-table-column prop="viewCount" label="浏览" width="90" />
            <el-table-column prop="favoriteCount" label="收藏" width="90" />
            <el-table-column prop="applyCount" label="投递" width="90" />
            <el-table-column label="上架" width="90">
              <template #default="{ row }">{{ row.shelfStatus === 1 ? '上架' : '下架' }}</template>
            </el-table-column>
          </el-table>
        </template>
      </el-card>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <el-card shadow="never">
            <template #header><span class="title">投递状态</span></template>
            <el-empty v-if="!statusTotal" description="还没有收到投递" />
            <EChart v-else :option="statusOption" height="320px" />
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="never">
            <template #header><span class="title">候选人技能</span></template>
            <el-empty v-if="!skills.length" description="投递者还没有技能标签" />
            <EChart v-else :option="skillOption" height="320px" />
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
import { getCompanyApplications, getCompanyDashboard, getCompanyInterviews } from '@/api/company'

const router = useRouter()
const pendingApps = ref(0)
const pendingInterviews = ref(0)

const loading = ref(true)
const board = ref({ jobs: [], applicationStatus: [], applicantSkills: [] })

const jobs = computed(() => board.value.jobs || [])
const statusRows = computed(() => board.value.applicationStatus || [])
const skills = computed(() => board.value.applicantSkills || [])
const statusTotal = computed(() => statusRows.value.reduce((sum, item) => sum + Number(item.count || 0), 0))
const chartJobs = computed(() => jobs.value.slice(0, 10))
const tiles = computed(() => {
  const online = jobs.value.filter((j) => j.shelfStatus === 1).length
  const applyTotal = jobs.value.reduce((sum, j) => sum + Number(j.applyCount || 0), 0)
  return [
    { label: '在架职位', value: online, sub: `共 ${jobs.value.length} 个职位`, path: '/company/jobs' },
    { label: '待初筛投递', value: pendingApps.value, sub: '点击开始筛选', path: '/company/candidates?status=0', urgent: true },
    { label: '待进行面试', value: pendingInterviews.value, sub: '笔试 / 面试', path: '/company/interviews', urgent: true },
    { label: '累计收到投递', value: applyTotal, sub: '全部职位合计', path: '/company/candidates' }
  ]
})
const shortTitle = (t) => (t && t.length > 14 ? `${t.slice(0, 14)}…` : t)

const jobOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { top: 0 },
  grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
  yAxis: {
    type: 'category',
    inverse: true,
    data: chartJobs.value.map((item) => shortTitle(item.title)),
    axisLabel: { interval: 0 }
  },
  xAxis: { type: 'value', minInterval: 1 },
  series: [
    { name: '浏览', type: 'bar', data: chartJobs.value.map((item) => item.viewCount || 0) },
    { name: '收藏', type: 'bar', data: chartJobs.value.map((item) => item.favoriteCount || 0) },
    { name: '投递', type: 'bar', data: chartJobs.value.map((item) => item.applyCount || 0) }
  ]
}))

const statusOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}（{d}%）' },
  legend: { bottom: 0 },
  series: [
    {
      name: '投递状态',
      type: 'funnel',
      left: '8%',
      width: '84%',
      sort: 'none',
      minSize: '15%',
      label: { formatter: '{b} {c}' },
      data: statusRows.value
        .filter((item) => Number(item.count) > 0)
        .map((item) => ({ name: item.label, value: Number(item.count) }))
    }
  ]
}))

const skillOption = computed(() => {
  const rows = [...skills.value].slice().reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 24, top: 12, bottom: 8, containLabel: true },
    xAxis: { type: 'value', name: '人数', minInterval: 1 },
    yAxis: { type: 'category', data: rows.map((item) => item.name) },
    series: [
      {
        name: '投递者',
        type: 'bar',
        data: rows.map((item) => Number(item.count || 0)),
        itemStyle: { color: '#67c23a', borderRadius: [0, 4, 4, 0] }
      }
    ]
  }
})

onMounted(async () => {
  Promise.allSettled([
    getCompanyApplications({ current: 1, size: 1, status: 0 }),
    getCompanyInterviews({ current: 1, size: 1, interviewStatus: 0 })
  ]).then(([a, i]) => {
    pendingApps.value = a.status === 'fulfilled' ? a.value?.total || 0 : 0
    pendingInterviews.value = i.status === 'fulfilled' ? i.value?.total || 0 : 0
  })
  try {
    board.value = (await getCompanyDashboard()) || board.value
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
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
.table {
  margin-top: 12px;
}
.el-row {
  row-gap: 16px;
}
.urgent .stat-value {
  color: #e6a23c;
}
.shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.shortcuts .el-button + .el-button {
  margin-left: 0;
}
</style>
