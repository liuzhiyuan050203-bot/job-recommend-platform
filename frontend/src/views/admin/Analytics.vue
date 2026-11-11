<template>
  <div class="page-container">
    <el-skeleton :loading="loading" animated>
      <template #template>
        <el-skeleton-item variant="rect" style="height: 88px; margin-bottom: 16px" />
        <el-skeleton-item variant="rect" style="height: 320px" />
      </template>
    <el-row :gutter="16">
      <el-col v-for="item in cards" :key="item.label" :xs="12" :sm="8" :md="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col v-for="item in insightCards" :key="item.label" :xs="12" :sm="8" :md="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">推荐评估（K=10）</span></template>
      <el-empty v-if="!ndcgRows.length" description="还没有推荐评估结果" />
      <EChart v-else :option="ndcgOption" height="300px" />
    </el-card>

    <el-alert type="info" :closable="false" show-icon>
      <template #title>
        以下统计由 Spark 离线批次计算（最近批次 {{ overview.lastBatchNo || '-' }}）。需要重新计算请到
        <el-button link type="primary" @click="router.push('/admin/spark')">Spark 任务</el-button>
        页面运行。
      </template>
    </el-alert>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header><span class="title">城市平均月薪</span></template>
          <el-empty v-if="!(salary.byCity || []).length" description="暂无城市薪资" />
          <EChart v-else :option="salaryOption" height="360px" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header><span class="title">技术需求趋势</span></template>
          <el-empty v-if="!(trend.months || []).length" description="暂无技术趋势" />
          <EChart v-else :option="trendOption" height="360px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">地区职位分布</span></template>
      <el-empty v-if="!region.length" description="暂无地区统计" />
      <template v-else>
      <EChart :option="regionOption" height="320px" />
      <el-table :data="region" size="small" empty-text="暂无地区统计" class="region-table">
        <el-table-column prop="name" label="省份" />
        <el-table-column prop="adcode" label="区划代码" />
        <el-table-column prop="value" label="职位数" />
        <el-table-column prop="companyCount" label="企业数" />
        <el-table-column label="平均月薪">
          <template #default="{ row }">{{ formatSalary(row.avgSalary) }}</template>
        </el-table-column>
        <el-table-column prop="applyCount" label="投递数" />
      </el-table>
      </template>
    </el-card>
    </el-skeleton>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import EChart from '@/components/EChart.vue'
import { getRegionStats, getSalaryStats, getStatsOverview, getTechTrend } from '@/api/public'
import { getAdminDashboard, getRecommendEval, getRecommendStats } from '@/api/admin'
import { knowledgeStats } from '@/api/ai'

const loading = ref(true)
const overview = ref({})
const salary = ref({ records: [], byDirection: [], byCity: [] })
const trend = ref({ months: [], series: [], ranking: [] })
const region = ref([])
const router = useRouter()
const recommendStats = ref({})
const recommendEval = ref({ metrics: [] })
const adminBoard = ref({ ai: {}, recommend: {} })
const knowledge = ref({})

const ALGO_LABEL = { cf: '协同过滤', content: '内容匹配', hybrid: '融合', popular: '热门' }

const cards = computed(() => {
  const data = overview.value || {}
  return [
    { label: '职位', value: display(data.jobCount) },
    { label: '企业', value: display(data.companyCount) },
    { label: '学生', value: display(data.studentCount) },
    { label: '投递', value: display(data.applicationCount) },
    { label: '城市', value: display(data.cityCount) },
    { label: '平均月薪', value: formatSalary(data.avgSalary) },
    { label: '最近批次', value: data.lastBatchNo || '-' }
  ]
})

const insightCards = computed(() => {
  const stats = recommendStats.value || {}
  const brief = adminBoard.value?.recommend || {}
  const ai = adminBoard.value?.ai || {}
  const ndcg = brief.ndcgAt10
  return [
    { label: '推荐 NDCG@10', value: percent(ndcg) },
    { label: '推荐覆盖率', value: percent(stats.coverage ?? brief.coverage) },
    { label: '推荐学生', value: display(stats.userCount ?? brief.userCount) },
    { label: 'AI 会话', value: display(ai.sessionCount) },
    { label: 'AI 消息', value: display(ai.messageCount) },
    { label: '知识文档', value: display(knowledge.value?.documents) }
  ]
})

const ndcgRows = computed(() => {
  const rows = (recommendEval.value.metrics || []).filter((item) => Number(item.k) === 10)
  const order = ['cf', 'content', 'hybrid', 'popular']
  return order.map((algo) => rows.find((item) => item.algo === algo)).filter(Boolean)
})

const ndcgOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (value) => `${value}%` },
  grid: { left: 12, right: 16, top: 16, bottom: 8, containLabel: true },
  xAxis: { type: 'category', data: ndcgRows.value.map((item) => ALGO_LABEL[item.algo] || item.algo) },
  yAxis: { type: 'value', name: '%', min: 0 },
  series: [
    {
      name: 'NDCG@10',
      type: 'bar',
      data: ndcgRows.value.map((item) => percentNumber(item.ndcgAtK)),
      itemStyle: { color: '#e6a23c', borderRadius: [4, 4, 0, 0] }
    }
  ]
}))

const salaryOption = computed(() => {
  const rows = [...(salary.value.byCity || [])].slice(0, 10).reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 24, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'value', name: '千元/月' },
    yAxis: { type: 'category', data: rows.map((item) => item.city) },
    series: [
      {
        name: '平均月薪',
        type: 'bar',
        data: rows.map((item) => roundK(item.avgSalary)),
        itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] }
      }
    ]
  }
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { type: 'scroll', top: 0 },
  grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
  xAxis: { type: 'category', boundaryGap: false, data: trend.value.months || [] },
  yAxis: { type: 'value', name: '职位数' },
  series: (trend.value.series || []).map((item) => ({
    name: item.name,
    type: 'line',
    smooth: true,
    data: item.data || []
  }))
}))

const regionOption = computed(() => {
  const rows = [...(region.value || [])].slice(0, 12).reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 24, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'value', name: '职位数' },
    yAxis: { type: 'category', data: rows.map((item) => item.name) },
    series: [
      {
        name: '职位数',
        type: 'bar',
        data: rows.map((item) => item.value),
        itemStyle: { color: '#67c23a', borderRadius: [0, 4, 4, 0] }
      }
    ]
  }
})

function display(value) {
  return value === 0 || value ? value : '-'
}

function percentNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 0
  return Math.round(number * 1000) / 10
}

function percent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return `${percentNumber(number)}%`
}

function formatSalary(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  if (Number.isNaN(number)) return '-'
  return `${Math.round(number).toLocaleString('zh-CN')} 元`
}

function roundK(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return 0
  return Math.round((number / 1000) * 10) / 10
}

async function loadBoard() {
  const [overviewData, salaryData, trendData, regionData] = await Promise.all([
    getStatsOverview(),
    getSalaryStats(),
    getTechTrend({ top: 6, months: 12 }),
    getRegionStats()
  ])
  overview.value = overviewData || {}
  salary.value = salaryData || { records: [], byDirection: [], byCity: [] }
  trend.value = trendData || { months: [], series: [], ranking: [] }
  region.value = regionData || []
}

async function loadInsights() {
  const tasks = await Promise.allSettled([
    getRecommendStats(),
    getRecommendEval(),
    getAdminDashboard(),
    knowledgeStats()
  ])
  const pick = (index) => (tasks[index].status === 'fulfilled' ? tasks[index].value : null)
  recommendStats.value = pick(0) || {}
  recommendEval.value = pick(1) || { metrics: [] }
  adminBoard.value = pick(2) || { ai: {}, recommend: {} }
  knowledge.value = pick(3) || {}
}

onMounted(async () => {
  try {
    await Promise.all([loadBoard(), loadInsights()])
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.stat-card {
  margin-bottom: 0;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.stat-value {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 600;
  word-break: break-all;
}
.region-table {
  margin-top: 12px;
}
</style>
