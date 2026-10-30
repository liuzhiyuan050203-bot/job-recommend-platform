<template>
  <div class="page-container">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">招聘漏斗转化分析</span>
            </div>
          </template>
          <EChart :option="funnelOption" height="320px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="title">候选人学历分布</span>
            </div>
          </template>
          <EChart :option="pieOption" height="320px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EChart from '@/components/EChart.vue'

const funnelOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b} : {c}%'
  },
  series: [
    {
      name: '招聘转化漏斗',
      type: 'funnel',
      left: '10%',
      top: 20,
      bottom: 20,
      width: '80%',
      min: 0,
      max: 100,
      minSize: '0%',
      maxSize: '100%',
      sort: 'descending',
      gap: 2,
      label: {
        show: true,
        position: 'inside'
      },
      emphasis: {
        label: {
          fontSize: 14
        }
      },
      data: [
        { value: 100, name: '收到简历 (120人)' },
        { value: 70, name: '初筛通过 (84人)' },
        { value: 45, name: '笔试/面试 (54人)' },
        { value: 20, name: '发意向Offer (24人)' },
        { value: 12, name: '最终录用 (15人)' }
      ]
    }
  ]
}))

const pieOption = computed(() => ({
  tooltip: {
    trigger: 'item'
  },
  legend: {
    top: 'bottom'
  },
  series: [
    {
      name: '学历分布',
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 16,
          fontWeight: 'bold'
        }
      },
      labelLine: {
        show: false
      },
      data: [
        { value: 58, name: '本科生' },
        { value: 36, name: '硕士研究生' },
        { value: 6, name: '博士及其他' }
      ]
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
