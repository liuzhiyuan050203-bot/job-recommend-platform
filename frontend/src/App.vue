<template>
  <router-view />
</template>

<script setup>
</script>

<style>
/* 全局基础重置样式 */
html,
body,
#app {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #f7fafc;
  color: #2d3748;
}

* {
  box-sizing: border-box;
}

/* 后台页面通用排版：卡片纵向间距、卡片头部、分页、工具条 */
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.page-container > .el-card {
  margin: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.card-header .title,
.page-title {
  font-weight: 600;
  font-size: 16px;
}

.card-header .hint,
.page-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.stat-tile {
  cursor: default;
}

.stat-tile.clickable {
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}

.stat-tile.clickable:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.stat-tile .stat-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.stat-tile .stat-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: #2d3748;
}

.stat-tile .stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.el-table .el-table__empty-text {
  line-height: 1.6;
}
</style>
