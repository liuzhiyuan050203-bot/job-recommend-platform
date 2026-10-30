<template>
  <div class="page-container">
    <el-row :gutter="20">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">全国热门高校毕业生就业技术热度趋势 (Spark 分析)</span>
            </div>
          </template>
          <EChart :option="trendOption" height="340px" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">城市平均薪资 Top 排行榜 (k/月)</span>
            </div>
          </template>
          <EChart :option="salaryRankOption" height="340px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EChart from '@/components/EChart.vue'

const trendOption = computed(() => ({
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['大数据/Spark', 'AI Agent/RAG', 'Java后端', '前端工程']
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['5月', '6月', '7月', '8月', '9月', '10月']
  },
  yAxis: {
    type: 'value',
    name: '需求指数'
  },
  series: [
    {
      name: '大数据/Spark',
      type: 'line',
      smooth: true,
      data: [120, 132, 161, 194, 230, 280]
    },
    {
      name: 'AI Agent/RAG',
      type: 'line',
      smooth: true,
      data: [90, 140, 200, 260, 340, 420]
    },
    {
      name: 'Java后端',
      type: 'line',
      smooth: true,
      data: [320, 332, 301, 334, 390, 360]
    },
    {
      name: '前端工程',
      type: 'line',
      smooth: true,
      data: [220, 232, 221, 254, 280, 270]
    }
  ]
}))

const salaryRankOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow'
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'value',
    name: 'k/月'
  },
  yAxis: {
    type: 'category',
    data: ['成都', '武汉', '杭州', '深圳', '上海', '北京']
  },
  series: [
    {
      name: '平均起薪',
      type: 'bar',
      data: [11.5, 12.0, 14.8, 16.2, 17.0, 17.8],
      itemStyle: {
        color: '#409eff',
        borderRadius: [0, 4, 4, 0]
      }
    }
  ]
}))
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
}
.title {
  font-weight: 600;
  font-size: 16px;
}
</style>
