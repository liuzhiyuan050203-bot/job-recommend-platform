<template>
  <AppLayout
    role-name="企业端"
    role-tag-type="success"
    :menu-items="menus"
    :audit-alert="auditAlert"
  />
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from './AppLayout.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const baseMenus = [
  { title: '企业资料与资质', path: '/company/profile', icon: 'OfficeBuilding' },
  { title: '招聘看板', path: '/company/dashboard', icon: 'DataAnalysis' },
  { title: '职位管理', path: '/company/jobs', icon: 'Briefcase' },
  { title: '候选人管理', path: '/company/candidates', icon: 'User' },
  { title: '面试安排', path: '/company/interviews', icon: 'Calendar' },
  { title: '招聘助手', path: '/company/assistant', icon: 'ChatLineRound' }
]

const auditPassed = computed(() => Number(userStore.companyAuditStatus) === 1)

const menus = computed(() => {
  if (auditPassed.value) {
    return baseMenus
  }
  return baseMenus.map((item) => ({
    ...item,
    disabled: item.path !== '/company/profile'
  }))
})

const auditAlert = computed(() => {
  if (userStore.roleName !== 'company' || auditPassed.value) {
    return ''
  }
  if (Number(userStore.companyAuditStatus) === 2) {
    return '企业资质未审核通过，审核已被驳回。请修改资料后重新提交，通过前只能使用「企业资料与资质」。'
  }
  return '企业资质未审核通过，当前为待审核。通过前只能使用「企业资料与资质」。'
})

function allows(path) {
  return path === '/company/profile' || path.startsWith('/company/profile/')
}

watch(
  () => userStore.companyAuditStatus,
  () => {
    if (!auditPassed.value && route.path.startsWith('/company') && !allows(route.path)) {
      router.replace('/company/profile')
    }
  }
)
</script>
