<template>
  <AppLayout
    role-name="管理员端"
    role-tag-type="danger"
    :menu-items="menus"
  />
</template>

<script setup>
import AppLayout from './AppLayout.vue'

const menus = [
  { title: '用户审核', path: '/admin/users', icon: 'UserFilled' },
  { title: '内容管理', path: '/admin/content', icon: 'Files' },
  { title: '数据大屏', path: '/admin/analytics', icon: 'TrendCharts' }
]
</script>
