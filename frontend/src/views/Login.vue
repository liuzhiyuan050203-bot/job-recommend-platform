<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand" @click="router.push('/')">高校就业推荐平台</div>
      <h2>账号登录</h2>
      <p class="auth-sub">学生、企业与管理员使用统一入口</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" maxlength="64" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
            maxlength="32"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button class="submit-btn" type="primary" native-type="submit" :loading="loading">登录</el-button>
      </el-form>

      <div class="auth-switch">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
      </div>

      <el-alert
        class="demo-alert"
        type="info"
        :closable="false"
        show-icon
        title="演示账号：admin / admin123，student / student123，company / company123"
      />
      <div class="demo-fill">
        <el-button link type="primary" native-type="button" @click="fill('admin', 'admin123')">填入管理员</el-button>
        <el-button link type="primary" native-type="button" @click="fill('student', 'student123')">填入学生</el-button>
        <el-button link type="primary" native-type="button" @click="fill('company', 'company123')">填入企业</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { isSafeRedirect, roleHome } from '@/utils/role'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const fill = (username, password) => {
  form.username = username
  form.password = password
}

const resolveTarget = (user) => {
  const redirect = route.query.redirect
  let target = isSafeRedirect(redirect, user.roleName) ? redirect : roleHome(user.roleName)
  if (user.roleName === 'company' && Number(user.companyAuditStatus) !== 1) {
    const path = String(target)
    if (!(path === '/company/profile' || path.startsWith('/company/profile/'))) {
      target = '/company/profile'
    }
  }
  return target
}

const handleLogin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const data = await userStore.login({
      username: form.username.trim(),
      password: form.password
    })
    ElMessage.success('登录成功')
    router.push(resolveTarget(data.user))
  } catch {
    // 拦截器已提示错误
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f7fafc;
}
.auth-card {
  width: 420px;
  max-width: 100%;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 32px 28px 24px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
}
.auth-brand {
  color: #409eff;
  font-weight: 700;
  cursor: pointer;
  margin-bottom: 12px;
}
h2 {
  margin: 0;
  font-size: 24px;
  color: #1a202c;
}
.auth-sub {
  margin: 8px 0 20px;
  color: #718096;
  font-size: 14px;
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
}
.auth-switch {
  margin-top: 16px;
  text-align: center;
  color: #4a5568;
  font-size: 14px;
}
.auth-switch a {
  color: #409eff;
  text-decoration: none;
}
.demo-alert {
  margin-top: 18px;
}
.demo-fill {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin-top: 8px;
}
</style>
