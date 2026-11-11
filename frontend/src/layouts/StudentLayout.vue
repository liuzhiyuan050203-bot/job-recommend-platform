<template>
  <AppLayout
    role-name="学生端"
    role-tag-type="primary"
    home-path="/student/home"
    :menu-groups="menus"
  >
    <template #banner>
      <el-alert
        v-if="nextInterview && route.path !== '/student/home'"
        class="interview-alert"
        type="warning"
        show-icon
        :closable="true"
      >
        <template #title>
          <span class="interview-line">
            近期安排：{{ nextInterview.interviewTime }} · {{ nextInterview.roundName }} ·
            {{ nextInterview.jobTitle }}（{{ nextInterview.companyName }}）
            <el-button link type="primary" @click="router.push('/student/applications')">查看投递进度</el-button>
          </span>
        </template>
      </el-alert>
    </template>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from './AppLayout.vue'
import { getUpcomingInterviews } from '@/api/student'

const route = useRoute()
const router = useRouter()

const menus = [
  {
    title: '工作台',
    items: [
      { title: '我的首页', path: '/student/home', icon: 'HomeFilled' },
      { title: '求职看板', path: '/student/dashboard', icon: 'DataAnalysis' }
    ]
  },
  {
    title: '找工作',
    items: [
      { title: '职位搜索', path: '/student/jobs', icon: 'Search' },
      { title: '为你推荐', path: '/student/recommend', icon: 'MagicStick' },
      { title: '我的收藏', path: '/student/favorites', icon: 'Star' },
      { title: '我的投递', path: '/student/applications', icon: 'Tickets' }
    ]
  },
  {
    title: '我的材料',
    items: [
      { title: '个人档案与技能', path: '/student/profile', icon: 'User' },
      { title: '在线简历', path: '/student/resume', icon: 'Document' }
    ]
  },
  {
    title: '求职工具',
    items: [
      { title: '薪资预测', path: '/student/salary', icon: 'Money' },
      { title: '就业助手', path: '/student/assistant', icon: 'ChatLineRound' },
      { title: '我的面经', path: '/student/community', icon: 'ChatDotRound' }
    ]
  }
]

const upcoming = ref([])
const nextInterview = computed(() => upcoming.value[0] || null)

onMounted(async () => {
  try {
    const list = await getUpcomingInterviews()
    upcoming.value = Array.isArray(list) ? list : []
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
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
</style>
