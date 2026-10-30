<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">职位管理与发布</span>
          <el-button type="primary" icon="Plus">发布新职位</el-button>
        </div>
      </template>

      <el-table :data="jobs" stripe style="width: 100%">
        <el-table-column prop="title" label="职位名称" min-width="150" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="salary" label="薪资区间" width="120" />
        <el-table-column prop="skills" label="技能标签" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="s in row.skills" :key="s" size="small" class="mr-1">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="上/下架状态" width="120">
          <template #default="{ row }">
            <el-switch
              v-model="row.online"
              active-text="上架"
              inactive-text="下架"
              inline-prompt
            />
          </template>
        </el-table-column>
        <el-table-column prop="applicantCount" label="已投递人数" width="110" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default>
            <el-button type="primary" size="small" link>编辑</el-button>
            <el-button type="info" size="small" link>查看候选人</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const jobs = ref([
  {
    title: '大数据开发工程师 (Spark)',
    category: '大数据方向',
    salary: '18k-30k',
    skills: ['PySpark', 'Hadoop', 'SQL'],
    online: true,
    applicantCount: 28
  },
  {
    title: 'Vue3 前端全栈开发',
    category: '前端工程',
    salary: '15k-24k',
    skills: ['Vue3', 'Vite', 'Pinia', 'Node.js'],
    online: true,
    applicantCount: 19
  },
  {
    title: '智能体 RAG 算法专家',
    category: '人工智能',
    salary: '25k-40k',
    skills: ['LangChain', 'ChromaDB', 'FastAPI'],
    online: false,
    applicantCount: 8
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
.mr-1 {
  margin-right: 4px;
}
</style>
