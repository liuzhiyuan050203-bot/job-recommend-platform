<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">投递记录与状态追踪</span>
          <el-tag type="warning">状态机流转：待初筛 → 笔试 → 面试中 → 已录用/未通过</el-tag>
        </div>
      </template>

      <el-timeline style="margin-top: 15px;">
        <el-timeline-item
          v-for="item in applications"
          :key="item.id"
          :timestamp="item.date"
          :type="item.statusType"
          placement="top"
        >
          <el-card>
            <div class="app-item-header">
              <span class="job-name">{{ item.jobTitle }} · {{ item.company }}</span>
              <el-tag :type="item.statusType" effect="light">{{ item.statusText }}</el-tag>
            </div>
            <p class="notice-text">
              <el-icon><Calendar /></el-icon> {{ item.reminder }}
            </p>
            <el-steps :active="item.stepIndex" finish-status="success" simple style="margin-top: 10px;">
              <el-step title="待初筛" />
              <el-step title="笔试阶段" />
              <el-step title="技术面试" />
              <el-step :title="item.finalTitle || '录取结果'" />
            </el-steps>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const applications = ref([
  {
    id: 1,
    jobTitle: '大数据开发工程师 (Spark)',
    company: '智能云科技术有限公司',
    date: '2026-10-28 10:30',
    statusText: '面试中',
    statusType: 'primary',
    stepIndex: 2,
    reminder: '面试日程：2026-11-02 14:00 线上视频面试，请提前调试摄像头与网络。',
    finalTitle: '录用待定'
  },
  {
    id: 2,
    jobTitle: 'AI Agent / RAG 研发工程师',
    company: '未来智能计算实验室',
    date: '2026-10-25 16:20',
    statusText: '已录用',
    statusType: 'success',
    stepIndex: 4,
    reminder: '恭喜！企业已发送录用意向书(Offer)，请于 3 个工作日内确认。',
    finalTitle: '已录用'
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
.app-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.job-name {
  font-weight: 600;
  font-size: 15px;
}
.notice-text {
  font-size: 13px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0 12px 0;
}
</style>
