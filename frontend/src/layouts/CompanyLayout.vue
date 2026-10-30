<template>
  <AppLayout
    role-name="企业端"
    role-tag-type="success"
    :menu-items="menus"
  />
</template>

<script setup>
import AppLayout from './AppLayout.vue'

const menus = [
  { title: '职位管理', path: '/company/jobs', icon: 'Briefcase' },
  { title: '候选人管理', path: '/company/candidates', icon: 'User' },
  { title: '数据看板', path: '/company/dashboard', icon: 'DataAnalysis' }
]
</script>
