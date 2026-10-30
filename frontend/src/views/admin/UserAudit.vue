<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">企业资质与账号认证审核</span>
          <el-button type="primary" plain size="small" icon="Refresh">刷新待审列表</el-button>
        </div>
      </template>

      <el-table :data="auditList" stripe style="width: 100%">
        <el-table-column prop="type" label="用户类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.type === '企业' ? 'success' : 'primary'">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="targetName" label="申请主体" min-width="160" />
        <el-table-column prop="license" label="营业执照 / 证明材料" min-width="150">
          <template #default>
            <el-button type="info" size="small" link icon="Document">查看证明材料.pdf</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="applyTime" label="申请时间" width="160" />
        <el-table-column prop="status" label="审核状态" width="110">
          <template #default="{ row }">
            <el-tag type="warning">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核操作" width="160" fixed="right">
          <template #default>
            <el-button type="success" size="small">通过</el-button>
            <el-button type="danger" size="small">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const auditList = ref([
  {
    type: '企业',
    targetName: '杭州智谱星辰科技有限公司',
    applyTime: '2026-10-29 11:20',
    status: '待审核'
  },
  {
    type: '企业',
    targetName: '深圳元象数据科技有限公司',
    applyTime: '2026-10-29 14:45',
    status: '待审核'
  },
  {
    type: '学生',
    targetName: '计算机学院 · 学历认证 (学信网)',
    applyTime: '2026-10-30 09:10',
    status: '待审核'
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
