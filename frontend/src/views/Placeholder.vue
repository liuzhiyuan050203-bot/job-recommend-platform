<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">{{ title }}</span>
          <el-tag type="info">开发中</el-tag>
        </div>
      </template>
      <el-empty :description="description" />
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => route.meta.title || '功能页面')
const description = computed(() => route.meta.desc || '该功能将在后续步骤中实现')
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
</style>
