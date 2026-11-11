<template>
  <AppLayout
    role-name="管理员端"
    role-tag-type="danger"
    home-path="/admin/dashboard"
    :menu-groups="menus"
  />
</template>

<script setup>
import AppLayout from './AppLayout.vue'

const menus = [
  {
    title: '工作台',
    items: [{ title: '管理首页', path: '/admin/dashboard', icon: 'HomeFilled' }]
  },
  {
    title: '审核与账号',
    items: [
      { title: '企业审核', path: '/admin/companies', icon: 'Stamp' },
      { title: '职位审核', path: '/admin/jobs', icon: 'DocumentChecked' },
      { title: '社区内容审核', path: '/admin/content', icon: 'Files' },
      { title: '用户管理', path: '/admin/users', icon: 'UserFilled' }
    ]
  },
  {
    title: '门户运营',
    items: [
      { title: '资讯文章', path: '/admin/articles', icon: 'Notebook' },
      { title: '首页轮播图', path: '/admin/banners', icon: 'Picture' }
    ]
  },
  {
    title: '基础数据',
    items: [
      { title: '职位分类', path: '/admin/categories', icon: 'Grid' },
      { title: '技能标签', path: '/admin/skills', icon: 'PriceTag' },
      { title: '知识库管理', path: '/admin/knowledge', icon: 'Reading' }
    ]
  },
  {
    title: '数据与算法',
    items: [
      { title: '就业分析', path: '/admin/analytics', icon: 'DataAnalysis' },
      { title: '投递总览', path: '/admin/applications', icon: 'List' },
      { title: 'Spark 任务', path: '/admin/spark', icon: 'Cpu' },
      { title: '推荐评估', path: '/admin/recommend', icon: 'Histogram' },
      { title: '数据助手', path: '/admin/assistant', icon: 'ChatLineRound' }
    ]
  }
]
</script>
