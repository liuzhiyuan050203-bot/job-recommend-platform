<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">职位检索与智能推荐 (User-CF / 内容匹配)</span>
          <el-tag type="info">Spark 离线计算与 RAG 赋能</el-tag>
        </div>
      </template>

      <!-- 搜索筛选区 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="技术方向">
          <el-select v-model="filters.category" placeholder="全部方向" clearable style="width: 140px;">
            <el-option label="Java开发" value="java" />
            <el-option label="大数据/Spark" value="bigdata" />
            <el-option label="前端开发" value="frontend" />
            <el-option label="人工智能/RAG" value="ai" />
          </el-select>
        </el-form-item>
        <el-form-item label="城市">
          <el-select v-model="filters.city" placeholder="全国" clearable style="width: 120px;">
            <el-option label="北京" value="beijing" />
            <el-option label="上海" value="shanghai" />
            <el-option label="深圳" value="shenzhen" />
            <el-option label="杭州" value="hangzhou" />
          </el-select>
        </el-form-item>
        <el-form-item label="薪资区间">
          <el-select v-model="filters.salary" placeholder="不限" clearable style="width: 130px;">
            <el-option label="10k-15k" value="1" />
            <el-option label="15k-25k" value="2" />
            <el-option label="25k-40k" value="3" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" icon="Search">检索职位</el-button>
          <el-button icon="MagicStick" type="success" plain>AI 智能匹配岗位</el-button>
        </el-form-item>
      </el-form>

      <!-- 职位列表演示 -->
      <el-table :data="mockJobs" stripe style="width: 100%">
        <el-table-column prop="title" label="职位名称" min-width="160">
          <template #default="{ row }">
            <span class="job-title">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="company" label="企业名称" min-width="140" />
        <el-table-column prop="city" label="城市" width="100" />
        <el-table-column prop="salary" label="薪资区间" width="120">
          <template #default="{ row }">
            <span class="salary-text">{{ row.salary }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="matchScore" label="推荐匹配度" width="130">
          <template #default="{ row }">
            <el-progress :percentage="row.matchScore" :status="row.matchScore >= 90 ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="技能标签" min-width="180">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag"
              size="small"
              class="mr-1"
            >
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default>
            <el-button type="primary" size="small" plain>投递简历</el-button>
            <el-button type="warning" size="small" link>收藏</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'

const filters = reactive({
  category: '',
  city: '',
  salary: ''
})

const mockJobs = ref([
  {
    title: '大数据开发工程师 (Spark/Flink)',
    company: '智能云科技术有限公司',
    city: '北京',
    salary: '18k-30k',
    matchScore: 95,
    tags: ['PySpark', 'Hadoop', 'Kafka', 'SQL']
  },
  {
    title: 'RAG 算法与应用研发工程师',
    company: '未来智能计算实验室',
    city: '杭州',
    salary: '22k-35k',
    matchScore: 92,
    tags: ['LangChain', 'Chroma', 'FastAPI', 'Python']
  },
  {
    title: 'Java 后端研发工程师',
    company: '鼎新互联科技',
    city: '深圳',
    salary: '15k-25k',
    matchScore: 84,
    tags: ['Spring Boot', 'MyBatis-Plus', 'MySQL', 'Redis']
  }
])
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.job-title {
  font-weight: 500;
  color: #303133;
}
.salary-text {
  color: #f56c6c;
  font-weight: 600;
}
.mr-1 {
  margin-right: 4px;
}
</style>
