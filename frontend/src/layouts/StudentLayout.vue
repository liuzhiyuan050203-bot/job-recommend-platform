<template>
  <AppLayout
    role-name="学生端"
    role-tag-type="primary"
    :menu-items="menus"
  >
    <template #banner>
      <el-alert
        v-if="upcoming.length"
        class="interview-alert"
        type="warning"
        show-icon
        :closable="false"
        title="即将到来的笔试 / 面试"
      >
        <div v-for="item in upcoming" :key="item.id" class="interview-line">
          <span>{{ item.interviewTime }}</span>
          <span>{{ item.roundName }}</span>
          <span>{{ item.jobTitle }}</span>
          <span>{{ item.companyName }}</span>
          <span v-if="item.interviewType === 1">{{ item.meetingUrl || '线上' }}</span>
          <span v-else>{{ item.location || '线下' }}</span>
        </div>
      </el-alert>
    </template>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AppLayout from './AppLayout.vue'
import { getUpcomingInterviews } from '@/api/student'

const menus = [
  { title: '首页', path: '/student/home', icon: 'HomeFilled' },
  { title: '职位搜索', path: '/student/jobs', icon: 'Search' },
  { title: '为你推荐', path: '/student/recommend', icon: 'MagicStick' },
  { title: '就业助手', path: '/student/assistant', icon: 'ChatLineRound' },
  { title: '我的收藏', path: '/student/favorites', icon: 'Star' },
  { title: '我的投递', path: '/student/applications', icon: 'Tickets' },
  { title: '在线简历', path: '/student/resume', icon: 'Document' },
  { title: '个人档案与技能', path: '/student/profile', icon: 'User' },
  { title: '面经社区', path: '/student/community', icon: 'ChatDotRound' }
]

const upcoming = ref([])

onMounted(async () => {
  try {
    const list = await getUpcomingInterviews()
    upcoming.value = Array.isArray(list) ? list.slice(0, 3) : []
  } catch {
    upcoming.value = []
  }
})
</script>

<style scoped>
.interview-alert {
  margin-bottom: 12px;
}
.interview-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  line-height: 1.8;
}
</style>
