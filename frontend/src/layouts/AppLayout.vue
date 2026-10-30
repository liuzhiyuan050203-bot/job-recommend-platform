<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="layout-aside">
      <div class="aside-logo" @click="router.push('/')">
        <el-icon class="logo-icon"><Briefcase /></el-icon>
        <span class="logo-title">就业推荐平台</span>
      </div>
      <div class="role-badge-box">
        <el-tag :type="roleTagType" effect="dark" size="small" class="role-tag">
          {{ roleName }}
        </el-tag>
      </div>
      <el-menu
        :default-active="route.path"
        router
        class="aside-menu"
        background-color="#1e222d"
        text-color="#a0aec0"
        active-text-color="#409eff"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
          :disabled="item.disabled"
        >
          <el-icon v-if="item.icon">
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ roleName }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentMenuTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button link type="primary" @click="router.push('/')">
            <el-icon><House /></el-icon> 返回门户首页
          </el-button>
          <el-divider direction="vertical" />
          <el-dropdown @command="handleUserCommand">
            <span class="user-info">
              <el-avatar :size="32" icon="UserFilled" class="user-avatar" />
              <span class="username">{{ displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="home">返回主页</el-dropdown-item>
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
import { computed, onMounted, reactive, ref } from 'vue'
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
  menuItems: {
    type: Array,
    required: true
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
const currentMenuTitle = computed(() => {
  const match = props.menuItems.find((item) => item.path === route.path)
  return match ? match.title : (route.meta.title || '当前页面')
})

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
  } else if (cmd === 'home') {
    router.push('/')
  } else if (cmd === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(() => {
  if (userStore.isLoggedIn) {
    userStore.fetchMe().catch(() => {})
  }
})
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  background-color: #f5f7fa;
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
}

.aside-logo {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  cursor: pointer;
  border-bottom: 1px solid #2d3748;
}

.logo-icon {
  font-size: 24px;
  color: #409eff;
}

.logo-title {
  font-size: 16px;
  font-weight: 600;
  color: #f7fafc;
}

.role-badge-box {
  padding: 12px 20px;
  border-bottom: 1px solid #2d3748;
}

.role-tag {
  letter-spacing: 1px;
}

.aside-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.layout-header {
  height: 60px;
  background-color: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
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
}

.layout-main {
  padding: 20px;
  overflow-y: auto;
}

.audit-alert {
  margin-bottom: 16px;
}
</style>
