<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">Spark 离线任务</span>
            <span class="hint head-hint">统计分析（薪资 / 技术趋势 / 地区分布）与混合推荐都在 Spark 中批量计算，结果写回 MySQL 供看板和推荐使用</span>
          </div>
          <div class="toolbar">
            <el-button type="primary" icon="DataAnalysis" :loading="runningAnalysis" @click="run('analysis')">运行统计分析</el-button>
            <el-button type="warning" icon="MagicStick" :loading="runningRecommend" @click="run('recommend')">重新生成推荐</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="hasRunning"
        type="info"
        show-icon
        :closable="false"
        class="running-alert"
        title="有批次正在运行，列表每 5 秒自动刷新。批次在后台子进程执行，离开页面不影响运行。"
      />

      <div class="toolbar filter-row">
        <el-radio-group v-model="status" size="small" @change="search">
          <el-radio-button :value="''">全部</el-radio-button>
          <el-radio-button :value="0">运行中</el-radio-button>
          <el-radio-button :value="1">成功</el-radio-button>
          <el-radio-button :value="2">失败</el-radio-button>
        </el-radio-group>
        <el-input v-model="batchNo" size="small" clearable placeholder="按批次号筛选" style="width: 220px" @keyup.enter="search" @clear="search" />
        <el-button size="small" icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" size="small" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand">
              <p><b>结果说明：</b>{{ row.resultMsg || '-' }}</p>
              <p v-if="row.errorMsg" class="error"><b>错误信息：</b>{{ row.errorMsg }}</p>
              <p v-if="row.paramsJson"><b>运行参数：</b><code>{{ row.paramsJson }}</code></p>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="batchNo" label="批次号" min-width="170" />
        <el-table-column prop="taskName" label="任务" min-width="130" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inputCount" label="输入行数" width="90" />
        <el-table-column prop="outputCount" label="输出行数" width="90" />
        <el-table-column label="开始时间" width="150">
          <template #default="{ row }">{{ fmt(row.startTime) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="80">
          <template #default="{ row }">{{ duration(row) }}</template>
        </el-table-column>
        <el-table-column prop="resultMsg" label="结果摘要" min-width="220" show-overflow-tooltip />
        <template #empty>
          <el-empty v-if="!loading" description="还没有任务记录，点击右上角按钮运行一次" />
        </template>
      </el-table>
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSparkTasks, runRecommend, runSparkAnalysis } from '@/api/admin'

const loading = ref(false)
const rows = ref([])
const status = ref('')
const batchNo = ref('')
const page = reactive({ current: 1, size: 10, total: 0 })
const runningAnalysis = ref(false)
const runningRecommend = ref(false)
let timer = null

const hasRunning = computed(() => rows.value.some((r) => r.status === 0))

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}
function statusText(s) {
  return { 0: '运行中', 1: '成功', 2: '失败' }[s] || '-'
}
function statusType(s) {
  return { 0: 'warning', 1: 'success', 2: 'danger' }[s] || 'info'
}
function duration(row) {
  if (!row.startTime) return '-'
  const end = row.endTime ? new Date(row.endTime) : new Date()
  const sec = Math.max(0, Math.round((end - new Date(row.startTime)) / 1000))
  return sec >= 60 ? `${Math.floor(sec / 60)}分${sec % 60}秒` : `${sec}秒`
}

async function load() {
  loading.value = !rows.value.length
  try {
    const res = await getSparkTasks({
      current: page.current,
      size: page.size,
      status: status.value === '' ? undefined : status.value,
      batchNo: batchNo.value.trim() || undefined
    })
    rows.value = res?.records || []
    page.total = res?.total || 0
  } catch {
    rows.value = []
  } finally {
    loading.value = false
    schedule()
  }
}

function schedule() {
  clearTimeout(timer)
  if (hasRunning.value) timer = setTimeout(load, 5000)
}

function search() {
  page.current = 1
  load()
}

async function run(kind) {
  const label = kind === 'analysis' ? '统计分析' : '推荐生成'
  const ok = await ElMessageBox.confirm(
    `将提交一个 Spark ${label}批次，约需 1~3 分钟，期间会占用较多 CPU。确定运行吗？`,
    `运行${label}`,
    { type: 'info', confirmButtonText: '运行', cancelButtonText: '取消' }
  ).then(() => true).catch(() => false)
  if (!ok) return
  const flag = kind === 'analysis' ? runningAnalysis : runningRecommend
  flag.value = true
  try {
    const data = kind === 'analysis' ? await runSparkAnalysis({}) : await runRecommend()
    if (data?.status === 'QUEUED') {
      ElMessage.success(`已有批次在运行，新批次 ${data.batchNo} 已排队`)
    } else {
      ElMessage.success(data?.batchNo ? `已提交批次 ${data.batchNo}` : '任务已提交')
    }
    status.value = ''
    page.current = 1
    setTimeout(load, 1500)
  } catch {
    // 拦截器已提示
  } finally {
    flag.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.title { font-weight: 600; }
.head-hint { display: block; margin-top: 4px; }
.running-alert { margin-bottom: 12px; }
.filter-row { margin-bottom: 12px; }
.expand { padding: 4px 48px; line-height: 1.7; color: var(--el-text-color-regular); }
.expand code { word-break: break-all; font-size: 12px; background: #f7fafc; padding: 2px 4px; }
.error { color: #f56c6c; }
</style>
