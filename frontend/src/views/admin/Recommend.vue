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
          <span class="title">推荐评估</span>
          <div class="actions">
            <el-radio-group v-model="k" size="small">
              <el-radio-button :value="5">K=5</el-radio-button>
              <el-radio-button :value="10">K=10</el-radio-button>
              <el-radio-button :value="20">K=20</el-radio-button>
            </el-radio-group>
            <el-button type="primary" :loading="running" @click="run">运行推荐任务</el-button>
          </div>
        </div>
      </template>
      <p v-if="evalData.summary" class="summary">{{ evalData.summary }}</p>
      <p v-else class="summary">还没有评估结果。运行后会比较协同过滤、内容匹配、融合和热门基线。</p>
      <EChart :option="chartOption" height="360px" />
      <el-table :data="tableRows" size="small" empty-text="暂无评估" class="metric-table">
        <el-table-column label="算法" min-width="120">
          <template #default="{ row }">{{ algoLabel(row.algo) }}</template>
        </el-table-column>
        <el-table-column prop="k" label="K" width="70" />
        <el-table-column label="Precision@K" min-width="120">
          <template #default="{ row }">{{ percent(row.precisionAtK) }}</template>
        </el-table-column>
        <el-table-column label="Recall@K" min-width="120">
          <template #default="{ row }">{{ percent(row.recallAtK) }}</template>
        </el-table-column>
        <el-table-column label="NDCG@K" min-width="120">
          <template #default="{ row }">{{ percent(row.ndcgAtK) }}</template>
        </el-table-column>
        <el-table-column label="覆盖率" min-width="100">
          <template #default="{ row }">{{ percent(row.coverage) }}</template>
        </el-table-column>
        <el-table-column prop="userCount" label="评估学生" width="100" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import EChart from '@/components/EChart.vue'
import { getRecommendEval, getRecommendStats, runRecommend } from '@/api/admin'

const ALGO_LABEL = {
  cf: '协同过滤',
  content: '内容匹配',
  hybrid: '融合',
  popular: '热门'
}
const ALGO_ORDER = ['cf', 'content', 'hybrid', 'popular']

const evalData = ref({ metrics: [] })
const stats = ref({})
const running = ref(false)
const k = ref(10)
let timer = null

const cards = computed(() => {
  const data = stats.value || {}
  const method = evalData.value.cfMethod === 'als' ? 'ALS' : (evalData.value.cfMethod === 'user_cosine' ? '用户余弦' : '-')
  return [
    { label: '批次', value: data.batchNo || evalData.value.batchNo || '-' },
    { label: '覆盖学生', value: display(data.userCount) },
    { label: '推荐条数', value: display(data.recommendCount) },
    { label: '职位覆盖', value: percent(data.coverage) },
    { label: '协同过滤', value: method },
    { label: '融合权重', value: evalData.value.alpha == null ? '-' : Number(evalData.value.alpha).toFixed(2) }
  ]
})

const tableRows = computed(() => {
  const rows = evalData.value.metrics || []
  return [...rows].sort((a, b) => {
    const ka = ALGO_ORDER.indexOf(a.algo)
    const kb = ALGO_ORDER.indexOf(b.algo)
    if (ka !== kb) return ka - kb
    return Number(a.k) - Number(b.k)
  })
})

const chartOption = computed(() => {
  const rows = (evalData.value.metrics || []).filter((item) => Number(item.k) === Number(k.value))
  const ordered = ALGO_ORDER.map((algo) => rows.find((item) => item.algo === algo)).filter(Boolean)
  const names = ordered.map((item) => algoLabel(item.algo))
  const seriesOf = (field, name) => ({
    name,
    type: 'bar',
    data: ordered.map((item) => percentNumber(item[field]))
  })
  return {
    tooltip: { trigger: 'axis', valueFormatter: (value) => `${value}%` },
    legend: { top: 0 },
    grid: { left: 12, right: 16, top: 40, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value', name: '%', min: 0 },
    series: [
      seriesOf('precisionAtK', 'Precision'),
      seriesOf('recallAtK', 'Recall'),
      seriesOf('ndcgAtK', 'NDCG'),
      seriesOf('coverage', '覆盖率')
    ]
  }
})

function algoLabel(algo) {
  return ALGO_LABEL[algo] || algo || '-'
}

function percentNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return 0
  return Math.round(num * 10000) / 100
}

function percent(value) {
  if (value == null || value === '') return '-'
  const num = Number(value)
  return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : '-'
}

function display(value) {
  return value == null || value === '' ? '-' : value
}

async function load() {
  const [evalResult, statResult] = await Promise.all([getRecommendEval(), getRecommendStats()])
  evalData.value = evalResult || { metrics: [] }
  stats.value = statResult || {}
}

function stopPoll() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function run() {
  running.value = true
  try {
    const data = await runRecommend()
    const batchNo = data?.batchNo
    ElMessage.success(batchNo ? `已提交批次 ${batchNo}` : '推荐任务已提交')
    stopPoll()
    const started = Date.now()
    timer = setInterval(async () => {
      try {
        const latest = await getRecommendEval()
        const statsNow = await getRecommendStats()
        if (latest?.batchNo && (!batchNo || latest.batchNo === batchNo) && (latest.metrics || []).length) {
          evalData.value = latest
          stats.value = statsNow || {}
          if (!batchNo || latest.batchNo === batchNo) {
            stopPoll()
            running.value = false
            ElMessage.success('推荐任务已完成')
          }
        }
      } catch {
        // 轮询失败时保留已提交提示
      }
      if (Date.now() - started > 180000) {
        stopPoll()
        running.value = false
        ElMessage.info('任务仍在运行，可稍后刷新查看')
      }
    }, 5000)
  } catch {
    running.value = false
  }
}

onMounted(async () => {
  try {
    await load()
  } catch {
    // 拦截器已提示
  }
})

onBeforeUnmount(stopPoll)
</script>

<style scoped>
.page-container { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.title { font-weight: 600; font-size: 16px; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { margin-top: 6px; font-size: 18px; font-weight: 600; word-break: break-all; }
.summary { color: var(--el-text-color-secondary); line-height: 1.6; margin-top: 0; }
.metric-table { margin-top: 12px; }
</style>
