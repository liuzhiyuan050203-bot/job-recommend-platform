<template>
  <el-container class="layout-container" :class="{ 'is-collapsed': collapsed }">
    <el-aside :width="collapsed ? '64px' : '220px'" class="layout-aside">
      <div class="aside-logo" title="返回门户首页" @click="router.push('/')">
        <el-icon class="logo-icon"><Briefcase /></el-icon>
        <span v-show="!collapsed" class="logo-title">就业推荐平台</span>
      </div>
      <div v-show="!collapsed" class="role-badge-box">
        <el-tag :type="roleTagType" effect="dark" size="small" class="role-tag">
          {{ roleName }}
        </el-tag>
        <span class="role-user" :title="displayName">{{ displayName }}</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="aside-menu"
        background-color="#1e222d"
        text-color="#a0aec0"
        active-text-color="#409eff"
      >
        <template v-for="group in groups" :key="group.title">
          <el-menu-item-group v-if="!collapsed && group.title">
            <template #title><span class="group-title">{{ group.title }}</span></template>
            <el-menu-item
              v-for="item in group.items"
              :key="item.path"
              :index="item.path"
              :disabled="item.disabled"
            >
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </el-menu-item>
          </el-menu-item-group>
          <template v-else>
            <el-menu-item
              v-for="item in group.items"
              :key="item.path"
              :index="item.path"
              :disabled="item.disabled"
            >
              <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>
          </template>
        </template>
      </el-menu>
    </el-aside>

    <el-container class="layout-body">
      <el-header class="layout-header">
        <div class="header-left">
          <el-button link class="collapse-btn" :title="collapsed ? '展开菜单' : '收起菜单'" @click="collapsed = !collapsed">
            <el-icon :size="18"><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: homePath }">{{ roleName }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentGroup && currentGroup.title">{{ currentGroup.title }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentItem && isDetail" :to="{ path: currentItem.path }">{{ currentItem.title }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button link type="primary" @click="router.push('/')">
            <el-icon><House /></el-icon><span class="hide-narrow">门户首页</span>
          </el-button>
          <el-divider direction="vertical" />
          <el-dropdown @command="handleUserCommand">
            <span class="user-info">
              <el-avatar :size="30" icon="UserFilled" class="user-avatar" />
              <span class="username hide-narrow">{{ displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="workbench">我的工作台</el-dropdown-item>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="demo">系统演示说明</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="layout-main">
        <el-alert
          v-if="auditAlert"
          class="audit-alert"
          :title="auditAlert"
          type="warning"
          show-icon
          :closable="false"
        />
        <slot name="banner" />
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <el-dialog v-model="pwdVisible" title="修改密码" width="420px" @closed="resetPasswordForm">
    <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
      <el-form-item label="原密码" prop="oldPassword">
        <el-input v-model="pwdForm.oldPassword" type="password" show-password maxlength="32" autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="pwdForm.newPassword" type="password" show-password maxlength="32" autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input v-model="pwdForm.confirmPassword" type="password" show-password maxlength="32" autocomplete="new-password" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="pwdVisible = false">取消</el-button>
      <el-button type="primary" :loading="pwdLoading" @click="submitPassword">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { updatePassword } from '@/api/user'

const props = defineProps({
  roleName: {
    type: String,
    required: true
  },
  roleTagType: {
    type: String,
    default: 'primary'
  },
  /** 分组菜单：[{ title: '找工作', items: [{ title, path, icon, disabled }] }] */
  menuGroups: {
    type: Array,
    required: true
  },
  homePath: {
    type: String,
    default: '/'
  },
  auditAlert: {
    type: String,
    default: ''
  }
})

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const displayName = computed(() => userStore.nickname)
const groups = computed(() => props.menuGroups || [])
const activeMenu = computed(() => route.meta.activeMenu || route.path)
const currentGroup = computed(() => groups.value.find((g) => g.items.some((item) => item.path === activeMenu.value)) || null)
const currentItem = computed(() => currentGroup.value?.items.find((item) => item.path === activeMenu.value) || null)
const isDetail = computed(() => !!route.meta.activeMenu && route.meta.activeMenu !== route.path)
const pageTitle = computed(() => {
  if (isDetail.value) return route.meta.title || '详情'
  return currentItem.value ? currentItem.value.title : (route.meta.title || '当前页面')
})

// 笔记本窄屏（< 1200px）默认收起侧栏，只显示图标
const NARROW = 1200
const collapsed = ref(typeof window !== 'undefined' && window.innerWidth < NARROW)
let lastWide = !collapsed.value
function onResize() {
  const wide = window.innerWidth >= NARROW
  if (wide !== lastWide) {
    collapsed.value = !wide
    lastWide = wide
  }
}

const pwdVisible = ref(false)
const pwdLoading = ref(false)
const pwdFormRef = ref()
const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const validateConfirm = (_rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== pwdForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const pwdRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 32, message: '新密码长度需为 6-32 位', trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirm, trigger: 'blur' }]
}

const resetPasswordForm = () => {
  pwdForm.oldPassword = ''
  pwdForm.newPassword = ''
  pwdForm.confirmPassword = ''
  pwdFormRef.value?.clearValidate()
}

const submitPassword = async () => {
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return
  pwdLoading.value = true
  try {
    await updatePassword({
      oldPassword: pwdForm.oldPassword,
      newPassword: pwdForm.newPassword
    })
    ElMessage.success('密码修改成功')
    pwdVisible.value = false
  } catch {
    // 拦截器已提示
  } finally {
    pwdLoading.value = false
  }
}

const handleUserCommand = (cmd) => {
  if (cmd === 'password') {
    pwdVisible.value = true
  } else if (cmd === 'workbench') {
    router.push(props.homePath)
  } else if (cmd === 'demo') {
    router.push('/demo')
  } else if (cmd === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onBeforeUnmount(() => window.removeEventListener('resize', onResize))

onMounted(() => {
  window.addEventListener('resize', onResize)
  if (userStore.isLoggedIn) {
    userStore.fetchMe().catch(() => {})
  }
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background: linear-gradient(to right, #1e222d 220px, #f5f7fa 220px);
}

.layout-container.is-collapsed {
  background: linear-gradient(to right, #1e222d 64px, #f5f7fa 64px);
}

.layout-aside {
  background-color: #1e222d;
  color: #fff;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  overflow: hidden;
  transition: width 0.2s;
}

.aside-logo {
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 0 16px;
  cursor: pointer;
  border-bottom: 1px solid #2d3748;
}

.logo-icon {
  font-size: 22px;
  color: #409eff;
}

.logo-title {
  font-size: 16px;
  font-weight: 600;
  color: #f7fafc;
  white-space: nowrap;
}

.role-badge-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #2d3748;
}

.role-tag {
  letter-spacing: 1px;
  flex-shrink: 0;
}

.role-user {
  color: #cbd5e0;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aside-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.aside-menu :deep(.el-menu-item-group__title) {
  padding: 12px 0 4px 20px !important;
}

.group-title {
  font-size: 12px;
  color: #718096;
  letter-spacing: 1px;
}

.aside-menu :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
}

.layout-body {
  min-width: 0;
}

.layout-header {
  height: 56px;
  background-color: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px 0 12px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.collapse-btn {
  color: #4a5568;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}

.user-avatar {
  background-color: #409eff;
}

.username {
  font-size: 14px;
  color: #4a5568;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layout-main {
  padding: 20px;
  overflow-x: hidden;
}

.audit-alert {
  margin-bottom: 16px;
}

@media (max-width: 900px) {
  .hide-narrow {
    display: none;
  }
  .layout-main {
    padding: 12px;
  }
}
</style>
