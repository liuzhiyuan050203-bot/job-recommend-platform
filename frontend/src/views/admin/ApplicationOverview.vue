<template>
  <div class="page-container">
    <el-row :gutter="12" class="stats">
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.jobTotal }}</div><div>职位总数</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.jobPending }}</div><div>待审核职位</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.jobOnline }}</div><div>上架职位</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.applicationTotal }}</div><div>投递总数</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.companyTotal }}</div><div>企业数</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="num">{{ overview.studentTotal }}</div><div>学生数</div></el-card></el-col>
    </el-row>
    <el-row :gutter="12" class="stats">
      <el-col v-for="item in overview.applicationStatusCounts || []" :key="item.status" :span="4">
        <el-card shadow="hover"><div class="num">{{ item.count }}</div><div>{{ item.statusName }}</div></el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">全平台投递</span>
          <div class="filters">
            <el-select v-model="query.status" clearable placeholder="状态" style="width: 130px" @change="search">
              <el-option v-for="item in APP_STATUS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-input v-model="query.companyId" clearable placeholder="企业ID" style="width: 120px" />
            <el-input v-model="query.jobId" clearable placeholder="职位ID" style="width: 120px" />
            <el-input v-model="query.keyword" clearable placeholder="学生/职位/企业" style="width: 180px" @keyup.enter="search" />
            <el-button type="primary" @click="search">查询</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="studentName" label="学生" width="100" />
        <el-table-column prop="jobTitle" label="职位" min-width="160" />
        <el-table-column prop="companyName" label="企业" min-width="140" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="appTagType(row.status)">{{ row.statusName }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="applyTime" label="投递时间" width="170" />
        <el-table-column prop="updateTime" label="更新时间" width="170" />
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
import { onMounted, reactive, ref } from 'vue'
import { getAdminApplications, getAdminOverview } from '@/api/admin'
import { APP_STATUS, appTagType } from '@/utils/job'

const loading = ref(false)
const rows = ref([])
const overview = ref({ applicationStatusCounts: [] })
const query = reactive({ status: null, companyId: '', jobId: '', keyword: '' })
const page = reactive({ current: 1, size: 10, total: 0 })

async function load() {
  loading.value = true
  try {
    const res = await getAdminApplications({
      current: page.current,
      size: page.size,
      status: query.status === null || query.status === '' ? undefined : query.status,
      companyId: query.companyId || undefined,
      jobId: query.jobId || undefined,
      keyword: query.keyword.trim() || undefined
    })
    rows.value = res.records || []
    page.total = res.total || 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.current = 1
  load()
}

onMounted(async () => {
  overview.value = await getAdminOverview()
  load()
})
</script>

<style scoped>
.stats { margin-bottom: 12px; }
.num { font-size: 22px; font-weight: 700; }
.card-header { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center; }
.title { font-weight: 600; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
