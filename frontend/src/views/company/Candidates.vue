<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">候选人管理与初筛流转</span>
          <el-radio-group v-model="filterStatus" size="small">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="pending">待初筛</el-radio-button>
            <el-radio-button label="exam">笔试</el-radio-button>
            <el-radio-button label="interview">面试中</el-radio-button>
            <el-radio-button label="offer">已录用</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-table :data="candidates" stripe style="width: 100%">
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="jobTitle" label="应聘职位" min-width="160" />
        <el-table-column prop="education" label="学历 / 院校" min-width="160" />
        <el-table-column prop="matchScore" label="匹配度" width="100">
          <template #default="{ row }">
            <el-tag type="success">{{ row.matchScore }}%</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="当前阶段" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="流转操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link>安排面试</el-button>
            <el-button type="success" size="small" link>发 Offer</el-button>
            <el-button type="danger" size="small" link>淘汰</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const filterStatus = ref('all')

const candidates = ref([
  {
    name: '李华',
    jobTitle: '大数据开发工程师 (Spark)',
    education: '硕士 · 华中科技大学',
    matchScore: 94,
    status: '面试中'
  },
  {
    name: '王五',
    jobTitle: 'Vue3 前端全栈开发',
    education: '本科 · 武汉大学',
    matchScore: 89,
    status: '待初筛'
  },
  {
    name: '赵六',
    jobTitle: '智能体 RAG 算法专家',
    education: '硕士 · 浙江大学',
    matchScore: 96,
    status: '笔试阶段'
  }
])
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
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
