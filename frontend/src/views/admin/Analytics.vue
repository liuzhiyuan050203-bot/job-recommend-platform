<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col v-for="item in cards" :key="item.label" :xs="12" :sm="8" :md="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">Spark 离线分析</span>
          <el-button type="primary" :loading="running" @click="runAnalysis">运行 Spark 分析</el-button>
        </div>
      </template>
      <el-table :data="tasks" size="small" empty-text="还没有分析任务">
        <el-table-column prop="batchNo" label="批次" min-width="160" />
        <el-table-column prop="taskName" label="任务" min-width="140" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
        <el-table-column prop="inputCount" label="输入" width="80" />
        <el-table-column prop="outputCount" label="输出" width="80" />
        <el-table-column prop="resultMsg" label="结果" min-width="220" show-overflow-tooltip />
        <el-table-column prop="startTime" label="开始时间" min-width="170" />
      </el-table>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header><span class="title">城市平均月薪</span></template>
          <EChart :option="salaryOption" height="360px" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never">
          <template #header><span class="title">技术需求趋势</span></template>
          <EChart :option="trendOption" height="360px" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">地区职位分布</span></template>
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
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import EChart from '@/components/EChart.vue'
import { getRegionStats, getSalaryStats, getStatsOverview, getTechTrend } from '@/api/public'
import { getSparkTasks, runSparkAnalysis } from '@/api/admin'

const overview = ref({})
const salary = ref({ records: [], byDirection: [], byCity: [] })
const trend = ref({ months: [], series: [], ranking: [] })
const region = ref([])
const tasks = ref([])
const running = ref(false)

const cards = computed(() => {
  const data = overview.value || {}
  return [
    { label: '职位', value: display(data.jobCount) },
    { label: '企业', value: display(data.companyCount) },
    { label: '学生', value: display(data.studentCount) },
    { label: '城市', value: display(data.cityCount) },
    { label: '平均月薪', value: formatSalary(data.avgSalary) },
    { label: '最近批次', value: data.lastBatchNo || '-' }
  ]
})

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

function statusText(status) {
  if (status === 0) return '运行中'
  if (status === 1) return '成功'
  if (status === 2) return '失败'
  return '-'
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

async function loadTasks() {
  const page = await getSparkTasks({ current: 1, size: 8 })
  tasks.value = page?.records || []
}

async function runAnalysis() {
  running.value = true
  try {
    const data = await runSparkAnalysis({})
    ElMessage.success(data?.batchNo ? `已提交批次 ${data.batchNo}` : '分析任务已提交')
    await loadTasks()
  } catch {
    // 拦截器已提示
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadBoard(), loadTasks()])
  } catch {
    // 拦截器已提示
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
