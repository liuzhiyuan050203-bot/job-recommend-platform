<template>
  <AppLayout
    role-name="学生端"
    role-tag-type="primary"
    :menu-items="menus"
  />
</template>

<script setup>
import AppLayout from './AppLayout.vue'

const menus = [
  { title: '职位检索', path: '/student/jobs', icon: 'Search' },
  { title: '我的简历', path: '/student/resume', icon: 'Document' },
  { title: '投递记录', path: '/student/applications', icon: 'Tickets' }
]
</script>
