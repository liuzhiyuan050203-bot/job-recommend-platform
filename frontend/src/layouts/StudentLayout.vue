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
  { title: '首页', path: '/student/home', icon: 'HomeFilled' },
  { title: '职位搜索', path: '/student/jobs', icon: 'Search' },
  { title: '我的收藏', path: '/student/favorites', icon: 'Star' },
  { title: '我的投递', path: '/student/applications', icon: 'Tickets' },
  { title: '在线简历', path: '/student/resume', icon: 'Document' },
  { title: '个人档案与技能', path: '/student/profile', icon: 'User' },
  { title: '面经社区', path: '/student/community', icon: 'ChatDotRound' }
]
</script>
