<template>
  <div v-loading="loading" class="page-container">
    <el-row :gutter="16">
      <el-col v-for="t in todoTiles" :key="t.label" :xs="12" :sm="6">
        <el-card shadow="never" class="stat-tile clickable" :class="{ urgent: t.value > 0 }" @click="router.push(t.path)">
          <div class="stat-label">{{ t.label }}</div>
          <div class="stat-value">{{ t.value }}</div>
          <div class="stat-sub">{{ t.value > 0 ? '点击去处理' : '暂无待办' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="fill">
          <template #header>
            <div class="card-header">
              <span class="title">平台概况</span>
              <el-button link type="primary" @click="router.push('/admin/analytics')">就业分析</el-button>
            </div>
          </template>
          <div class="kpis">
            <div v-for="k in kpis" :key="k.label" class="kpi">
              <div class="kpi-value">{{ k.value }}</div>
              <div class="kpi-label">{{ k.label }}</div>
            </div>
          </div>
          <el-divider content-position="left">职位数据来源</el-divider>
          <div class="sources">
            <div v-for="s in sources" :key="s.code" class="source-row">
              <el-tag :type="s.type" effect="plain" class="source-tag">{{ s.label }}</el-tag>
              <el-progress :percentage="s.pct" :stroke-width="10" :show-text="false" class="source-bar" />
              <span class="source-num">{{ s.count }}</span>
              <el-button link type="primary" @click="router.push({ path: '/admin/jobs', query: { source: s.code } })">查看</el-button>
            </div>
            <p class="muted">「校招官网同步」与「外部来源」职位官网未公布薪资，前台统一标注为估算薪资；外部来源职位只能到企业官网投递。</p>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="fill">
          <template #header>
            <div class="card-header">
              <span class="title">离线计算与推荐</span>
              <el-button link type="primary" @click="router.push('/admin/spark')">Spark 任务</el-button>
            </div>
          </template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="最近批次">{{ board.spark?.taskName || '-' }}（{{ sparkStatus(board.spark?.status) }}）</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ fmt(board.spark?.endTime) }}</el-descriptions-item>
            <el-descriptions-item label="推荐 NDCG@10">{{ pct(board.recommend?.ndcgAt10) }}</el-descriptions-item>
            <el-descriptions-item label="推荐覆盖率">{{ pct(board.recommend?.coverage) }}</el-descriptions-item>
            <el-descriptions-item label="已推荐学生">{{ board.recommend?.userCount ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="AI 会话 / 消息">{{ board.ai?.sessionCount ?? '-' }} / {{ board.ai?.messageCount ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="title">常用入口</span></template>
      <div class="shortcuts">
        <div v-for="s in shortcuts" :key="s.path" class="shortcut" @click="router.push(s.path)">
          <el-icon :size="20" :color="s.color"><component :is="s.icon" /></el-icon>
          <span>{{ s.title }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAdminCompanies, getAdminComments, getAdminDashboard, getAdminJobs, getAdminOverview, getAdminPosts } from '@/api/admin'

const router = useRouter()
const loading = ref(true)
const overview = ref({})
const board = ref({})
const pending = ref({ companies: 0, jobs: 0, posts: 0, comments: 0 })
const sourceCounts = ref({ platform: 0, self_crawl: 0, ext_ats: 0 })

const todoTiles = computed(() => [
  { label: '待审核企业', value: pending.value.companies, path: '/admin/companies?auditStatus=0' },
  { label: '待审核职位', value: pending.value.jobs, path: '/admin/jobs?auditStatus=0' },
  { label: '待审核帖子', value: pending.value.posts, path: '/admin/content' },
  { label: '待审核评论', value: pending.value.comments, path: '/admin/content?tab=comments' }
])

const kpis = computed(() => {
  const o = overview.value || {}
  return [
    { label: '在架职位', value: o.jobOnline ?? '-' },
    { label: '职位总数', value: o.jobTotal ?? '-' },
    { label: '企业', value: o.companyTotal ?? '-' },
    { label: '学生', value: o.studentTotal ?? '-' },
    { label: '投递', value: o.applicationTotal ?? '-' },
    { label: '平均月薪', value: board.value.platform?.avgSalary ? `${Math.round(board.value.platform.avgSalary).toLocaleString('zh-CN')} 元` : '-' }
  ]
})

const sources = computed(() => {
  const c = sourceCounts.value
  const total = Math.max(1, c.platform + c.self_crawl + c.ext_ats)
  return [
    { code: 'platform', label: '企业发布', type: 'success', count: c.platform },
    { code: 'self_crawl', label: '校招官网同步', type: 'info', count: c.self_crawl },
    { code: 'ext_ats', label: '外部来源', type: 'warning', count: c.ext_ats }
  ].map((s) => ({ ...s, pct: Math.round((s.count / total) * 100) }))
})

const shortcuts = [
  { title: '企业审核', path: '/admin/companies', icon: 'Stamp', color: '#409eff' },
  { title: '职位审核', path: '/admin/jobs', icon: 'DocumentChecked', color: '#67c23a' },
  { title: '运行 Spark 分析', path: '/admin/spark', icon: 'Cpu', color: '#e6a23c' },
  { title: '推荐评估', path: '/admin/recommend', icon: 'Histogram', color: '#f56c6c' },
  { title: '知识库管理', path: '/admin/knowledge', icon: 'Reading', color: '#8e44ad' },
  { title: '发布资讯', path: '/admin/articles', icon: 'Notebook', color: '#909399' }
]

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}
function pct(v) {
  const n = Number(v)
  return v == null || !Number.isFinite(n) ? '-' : `${(n * 100).toFixed(1)}%`
}
function sparkStatus(s) {
  return { 0: '运行中', 1: '成功', 2: '失败' }[s] || '-'
}

onMounted(async () => {
  const total = (r) => (r.status === 'fulfilled' ? r.value?.total || 0 : 0)
  try {
    const res = await Promise.allSettled([
      getAdminOverview(),
      getAdminDashboard(),
      getAdminCompanies({ auditStatus: 0, current: 1, size: 1 }),
      getAdminJobs({ auditStatus: 0, current: 1, size: 1 }),
      getAdminPosts({ auditStatus: 0, current: 1, size: 1 }),
      getAdminComments({ auditStatus: 0, current: 1, size: 1 }),
      getAdminJobs({ source: 'platform', current: 1, size: 1 }),
      getAdminJobs({ source: 'self_crawl', current: 1, size: 1 }),
      getAdminJobs({ source: 'ext_ats', current: 1, size: 1 })
    ])
    overview.value = res[0].status === 'fulfilled' ? res[0].value || {} : {}
    board.value = res[1].status === 'fulfilled' ? res[1].value || {} : {}
    pending.value = { companies: total(res[2]), jobs: total(res[3]), posts: total(res[4]), comments: total(res[5]) }
    sourceCounts.value = { platform: total(res[6]), self_crawl: total(res[7]), ext_ats: total(res[8]) }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.el-row { row-gap: 16px; }
.fill { height: 100%; }
.title { font-weight: 600; }
.urgent .stat-value { color: #e6a23c; }
.kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; }
.kpi { background: #f7fafc; border-radius: 6px; padding: 12px; }
.kpi-value { font-size: 20px; font-weight: 600; }
.kpi-label { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 4px; }
.sources { display: flex; flex-direction: column; gap: 10px; }
.source-row { display: flex; align-items: center; gap: 10px; }
.source-tag { width: 96px; justify-content: center; }
.source-bar { flex: 1; }
.source-num { width: 56px; text-align: right; font-variant-numeric: tabular-nums; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; margin: 4px 0 0; }
.shortcuts { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.shortcut { display: flex; align-items: center; gap: 10px; padding: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; cursor: pointer; }
.shortcut:hover { border-color: var(--el-color-primary-light-5); background: #f8fbff; }
</style>
