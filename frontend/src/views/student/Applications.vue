<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">我的投递</span>
          <span class="hint">点击一行查看进度、状态记录和面试安排</span>
        </div>
      </template>
      <el-tabs v-model="activeTab" class="status-tabs" @tab-change="search">
        <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name">
          <template #label>
            {{ tab.label }}<span v-if="counts[tab.name] !== undefined" class="tab-count">{{ counts[tab.name] }}</span>
          </template>
        </el-tab-pane>
      </el-tabs>
      <el-table v-loading="loading" :data="rows" stripe class="clickable-table" @row-click="open">
        <el-table-column label="职位" min-width="200">
          <template #default="{ row }">
            <el-button link type="primary" class="job-link" @click.stop="goJob(row)">{{ row.jobTitle }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="companyName" label="企业" min-width="140" show-overflow-tooltip />
        <el-table-column label="当前状态" width="110">
          <template #default="{ row }">
            <el-tag :type="appTagType(row.status)">{{ row.statusName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="投递时间" width="170">
          <template #default="{ row }">{{ fmt(row.applyTime) }}</template>
        </el-table-column>
        <el-table-column label="最近更新" width="170">
          <template #default="{ row }">{{ fmt(row.updateTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="open(row)">查看进度</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" :description="activeTab === 'all' ? '还没有投递记录' : '该状态下暂无投递'">
            <el-button v-if="activeTab === 'all'" type="primary" @click="router.push('/student/jobs')">去找职位</el-button>
          </el-empty>
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

    <el-drawer v-model="drawer" title="投递进度" size="560px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <h3 class="drawer-title">{{ detail.jobTitle }} · {{ detail.companyName }}</h3>
          <el-steps :active="stepActive(detail.status)" :process-status="detail.status === 4 ? 'error' : 'process'" finish-status="success" align-center>
            <el-step title="已投递" />
            <el-step title="笔试" />
            <el-step title="面试" />
            <el-step :title="detail.status === 4 ? '未通过' : '录用'" />
          </el-steps>
          <p class="status-tip">{{ statusTip(detail.status) }}</p>
          <h4>面试安排</h4>
          <el-empty v-if="!(detail.interviews || []).length" :image-size="60" description="暂无笔试 / 面试安排" />
          <el-card v-for="item in detail.interviews || []" :key="item.id" class="interview" shadow="never">
            <div class="iv-head">
              <b>{{ item.interviewTime }}</b> · {{ item.roundName }} · {{ item.interviewTypeName }}
              <el-tag size="small" :type="item.interviewStatus === 0 ? 'warning' : 'info'">{{ item.interviewStatusName }}</el-tag>
            </div>
            <div v-if="item.interviewType === 1">
              会议链接：
              <a v-if="isUrl(item.meetingUrl)" :href="item.meetingUrl" target="_blank" rel="noopener noreferrer">{{ item.meetingUrl }}</a>
              <span v-else>{{ item.meetingUrl || '待企业通知' }}</span>
            </div>
            <div v-else>地点：{{ item.location || '待企业通知' }}</div>
            <div v-if="item.contactName">联系人：{{ item.contactName }} {{ item.contactPhone }}</div>
            <div v-if="item.remark" class="muted">备注：{{ item.remark }}</div>
          </el-card>
          <h4>状态记录</h4>
          <el-timeline>
            <el-timeline-item v-for="log in detail.logs || []" :key="log.id" :timestamp="fmt(log.createTime)">
              {{ log.fromStatusName || '提交投递' }} → {{ log.toStatusName }}
              <div class="muted">{{ log.operatorName }} {{ log.remark }}</div>
            </el-timeline-item>
          </el-timeline>
          <el-button @click="goJob(detail)">查看职位详情</el-button>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getApplication, getApplications } from '@/api/student'
import { APP_STATUS, appTagType } from '@/utils/job'

const router = useRouter()
const loading = ref(false)
const detailLoading = ref(false)
const rows = ref([])
const drawer = ref(false)
const detail = ref(null)
const page = reactive({ current: 1, size: 10, total: 0 })
const tabs = [{ name: 'all', label: '全部' }, ...APP_STATUS.map((s) => ({ name: String(s.value), label: s.label }))]
const activeTab = ref('all')
const counts = reactive({})

function fmt(v) {
  return v ? String(v).replace('T', ' ').slice(0, 16) : '-'
}

function isUrl(v) {
  return /^https?:\/\//i.test(v || '')
}

function stepActive(status) {
  if (status === 3) return 4
  if (status === 4) return 3
  return (status || 0) + 1
}

function statusTip(status) {
  return {
    0: '简历已送达，等待企业初筛。',
    1: '已进入笔试环节，请留意下方安排。',
    2: '已进入面试环节，请按时参加。',
    3: '恭喜，企业已决定录用！',
    4: '很遗憾本次未通过，可以继续关注其他职位。'
  }[status] || ''
}

async function load() {
  loading.value = true
  try {
    const status = activeTab.value === 'all' ? undefined : Number(activeTab.value)
    const res = await getApplications({ current: page.current, size: page.size, status })
    rows.value = res.records || []
    page.total = res.total || 0
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadCounts() {
  const results = await Promise.allSettled(tabs.map((t) => getApplications({ current: 1, size: 1, status: t.name === 'all' ? undefined : Number(t.name) })))
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') counts[tabs[i].name] = r.value?.total || 0
  })
}

function search() {
  page.current = 1
  load()
}

async function open(row) {
  drawer.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getApplication(row.id)
  } catch {
    drawer.value = false
  } finally {
    detailLoading.value = false
  }
}

function goJob(row) {
  const id = row.positionId || row.jobId
  if (id) router.push(`/student/jobs/${id}`)
}

onMounted(() => {
  load()
  loadCounts()
})
</script>

<style scoped>
.status-tabs { margin-top: -8px; }
.tab-count { margin-left: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
.clickable-table :deep(.el-table__row) { cursor: pointer; }
.job-link { font-weight: 500; white-space: normal; text-align: left; height: auto; }
.drawer-title { margin-top: 0; }
.status-tip { color: var(--el-text-color-regular); text-align: center; margin: 12px 0 0; font-size: 13px; }
.interview { margin-bottom: 8px; line-height: 1.8; }
.iv-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.muted { color: var(--el-text-color-secondary); }
h4 { margin: 18px 0 8px; }
</style>
