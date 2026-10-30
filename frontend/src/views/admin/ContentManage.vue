<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">内容与社区管理（轮播图、双选会公告、政策、面经审核）</span>
          <el-button type="primary" size="small" icon="Plus">发布新公告/政策</el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="双选会与就业政策" name="announcements">
          <el-table :data="announcements" stripe style="width: 100%">
            <el-table-column prop="title" label="标题" min-width="200" />
            <el-table-column prop="type" label="类别" width="130">
              <template #default="{ row }">
                <el-tag :type="row.type === '双选会' ? 'success' : 'info'">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="date" label="发布日期" width="140" />
            <el-table-column label="操作" width="140" fixed="right">
              <template #default>
                <el-button type="primary" size="small" link>编辑</el-button>
                <el-button type="danger" size="small" link>删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="面经与评论社区审核" name="reviews">
          <el-table :data="reviews" stripe style="width: 100%">
            <el-table-column prop="author" label="发布人" width="120" />
            <el-table-column prop="title" label="面经标题 / 评论内容" min-width="220" />
            <el-table-column prop="company" label="关联企业" width="160" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === '正常' ? 'success' : 'warning'">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default>
                <el-button type="danger" size="small" link>违规下架</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('announcements')

const announcements = ref([
  {
    title: '2026 届高校春季大型线上线下双选会邀请函',
    type: '双选会',
    date: '2026-10-25'
  },
  {
    title: '高校毕业生就业创业补贴政策汇总与申请指南',
    type: '就业政策',
    date: '2026-10-18'
  }
])

const reviews = ref([
  {
    author: '2026届小王',
    title: '腾讯云大数据开发面经（共三轮+HR面全复盘）',
    company: '腾讯科技',
    status: '正常'
  },
  {
    author: '匿名前端同学',
    title: '公司团队氛围很好，导师1对1带教，技术栈比较现代化',
    company: '字节跳动',
    status: '正常'
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
