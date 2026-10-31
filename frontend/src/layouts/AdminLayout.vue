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
  { title: '用户管理', path: '/admin/users', icon: 'UserFilled' },
  { title: '企业审核', path: '/admin/companies', icon: 'Stamp' },
  { title: '职位审核', path: '/admin/jobs', icon: 'DocumentChecked' },
  { title: '内容审核', path: '/admin/content', icon: 'Files' },
  { title: '轮播图', path: '/admin/banners', icon: 'Picture' },
  { title: '文章', path: '/admin/articles', icon: 'Notebook' },
  { title: '职位分类', path: '/admin/categories', icon: 'Grid' },
  { title: '技能标签', path: '/admin/skills', icon: 'PriceTag' },
  { title: '投递总览', path: '/admin/applications', icon: 'List' },
  { title: '就业分析', path: '/admin/analytics', icon: 'DataAnalysis' },
  { title: '推荐评估', path: '/admin/recommend', icon: 'Histogram' }
]
</script>
