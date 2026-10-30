<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header><span class="title">我的投递</span></template>
      <el-table v-loading="loading" :data="rows" stripe @row-click="open">
        <el-table-column prop="jobTitle" label="职位" min-width="160" />
        <el-table-column prop="companyName" label="企业" min-width="140" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="appTagType(row.status)">{{ row.statusName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updateTime" label="最近更新" width="180" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="open(row)">详情</el-button>
          </template>
        </el-table-column>
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
      <template v-if="detail">
        <h3>{{ detail.jobTitle }} · {{ detail.companyName }}</h3>
        <el-steps :active="stepActive(detail.status)" :process-status="detail.status === 4 ? 'error' : 'process'" finish-status="success" align-center>
          <el-step title="待初筛" />
          <el-step title="笔试" />
          <el-step title="面试中" />
          <el-step :title="detail.status === 4 ? '未通过' : '已录用'" />
        </el-steps>
        <h4>状态日志</h4>
        <el-timeline>
          <el-timeline-item v-for="log in detail.logs || []" :key="log.id" :timestamp="log.createTime">
            {{ log.fromStatusName || '新建' }} → {{ log.toStatusName }}
            <div>{{ log.operatorName }} {{ log.remark }}</div>
          </el-timeline-item>
        </el-timeline>
        <h4>面试安排</h4>
        <el-empty v-if="!(detail.interviews || []).length" description="暂无安排" />
        <el-card v-for="item in detail.interviews || []" :key="item.id" class="interview" shadow="never">
          <div>{{ item.interviewTime }} · {{ item.roundName }} · {{ item.interviewTypeName }} · {{ item.interviewStatusName }}</div>
          <div>{{ item.interviewType === 1 ? item.meetingUrl : item.location }}</div>
          <div v-if="item.contactName">联系人 {{ item.contactName }} {{ item.contactPhone }}</div>
          <div v-if="item.remark">{{ item.remark }}</div>
        </el-card>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getApplication, getApplications } from '@/api/student'
import { appTagType } from '@/utils/job'

const loading = ref(false)
const rows = ref([])
const drawer = ref(false)
const detail = ref(null)
const page = reactive({ current: 1, size: 10, total: 0 })

function stepActive(status) {
  if (status === 3) return 4
  if (status === 4) return 3
  return status || 0
}

async function load() {
  loading.value = true
  try {
    const res = await getApplications({ current: page.current, size: page.size })
    rows.value = res.records || []
    page.total = res.total || 0
  } finally {
    loading.value = false
  }
}

async function open(row) {
  detail.value = await getApplication(row.id)
  drawer.value = true
}

onMounted(load)
</script>

<style scoped>
.title { font-weight: 600; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
.interview { margin-bottom: 8px; }
h4 { margin: 16px 0 8px; }
</style>
