<template>
  <div class="page-container">
    <el-skeleton :loading="loading" animated>
      <template #template>
        <el-skeleton-item variant="rect" style="height: 320px" />
      </template>
      <el-card shadow="never">
        <template #header><span class="title">职位表现</span></template>
        <el-empty v-if="!jobs.length" description="还没有发布职位" />
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
import EChart from '@/components/EChart.vue'
import { getCompanyDashboard } from '@/api/company'

const loading = ref(true)
const board = ref({ jobs: [], applicationStatus: [], applicantSkills: [] })

const jobs = computed(() => board.value.jobs || [])
const statusRows = computed(() => board.value.applicationStatus || [])
const skills = computed(() => board.value.applicantSkills || [])
const statusTotal = computed(() => statusRows.value.reduce((sum, item) => sum + Number(item.count || 0), 0))
const chartJobs = computed(() => jobs.value.slice(0, 10))

const jobOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { top: 0 },
  grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
  xAxis: {
    type: 'category',
    data: chartJobs.value.map((item) => item.title),
    axisLabel: { interval: 0, rotate: 20 }
  },
  yAxis: { type: 'value', minInterval: 1 },
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
</style>
