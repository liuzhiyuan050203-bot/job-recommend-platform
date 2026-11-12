<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand" @click="router.push('/')">高校就业推荐平台</div>
      <h2>注册账号</h2>
      <p class="auth-sub">学生注册后可直接使用；企业需等待资质审核。管理员不开放注册。</p>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="学生注册" name="student">
          <el-form ref="studentFormRef" :model="studentForm" :rules="studentRules" label-position="top">
            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="用户名" prop="username">
                  <el-input v-model="studentForm.username" maxlength="64" placeholder="字母开头，3-64 位" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="昵称" prop="nickname">
                  <el-input v-model="studentForm.nickname" maxlength="64" placeholder="显示名称" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="密码" prop="password">
                  <el-input v-model="studentForm.password" type="password" show-password maxlength="32" autocomplete="new-password" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="确认密码" prop="confirmPassword">
                  <el-input v-model="studentForm.confirmPassword" type="password" show-password maxlength="32" autocomplete="new-password" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="真实姓名" prop="realName">
                  <el-input v-model="studentForm.realName" maxlength="64" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="性别" prop="gender">
                  <el-select v-model="studentForm.gender" style="width: 100%">
                    <el-option v-for="item in genderOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学历" prop="education">
                  <el-select v-model="studentForm.education" placeholder="请选择" style="width: 100%">
                    <el-option v-for="item in educationOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="毕业年份" prop="graduationYear">
                  <el-input-number v-model="studentForm.graduationYear" :min="2000" :max="2100" controls-position="right" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="手机号" prop="phone">
                  <el-input v-model="studentForm.phone" maxlength="11" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="邮箱" prop="email">
                  <el-input v-model="studentForm.email" maxlength="128" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学校" prop="school">
                  <el-input v-model="studentForm.school" maxlength="128" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学院" prop="college">
                  <el-input v-model="studentForm.college" maxlength="128" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="专业" prop="major">
                  <el-input v-model="studentForm.major" maxlength="128" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学号" prop="studentNo">
                  <el-input v-model="studentForm.studentNo" maxlength="32" placeholder="选填" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="企业注册" name="company">
          <el-form ref="companyFormRef" :model="companyForm" :rules="companyRules" label-position="top">
            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="用户名" prop="username">
                  <el-input v-model="companyForm.username" maxlength="64" placeholder="字母开头，3-64 位" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="企业全称" prop="companyName">
                  <el-input v-model="companyForm.companyName" maxlength="128" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="密码" prop="password">
                  <el-input v-model="companyForm.password" type="password" show-password maxlength="32" autocomplete="new-password" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="确认密码" prop="confirmPassword">
                  <el-input v-model="companyForm.confirmPassword" type="password" show-password maxlength="32" autocomplete="new-password" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="企业简称" prop="shortName">
                  <el-input v-model="companyForm.shortName" maxlength="64" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="统一社会信用代码" prop="creditCode">
                  <el-input v-model="companyForm.creditCode" maxlength="18" placeholder="18 位，如 91330100MA2AB1C23D" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="联系人" prop="contactName">
                  <el-input v-model="companyForm.contactName" maxlength="64" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="联系电话" prop="contactPhone">
                  <el-input v-model="companyForm.contactPhone" maxlength="11" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="联系邮箱" prop="contactEmail">
                  <el-input v-model="companyForm.contactEmail" maxlength="128" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="所属行业" prop="industry">
                  <el-input v-model="companyForm.industry" maxlength="64" placeholder="选填" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="省份" prop="province">
                  <el-input v-model="companyForm.province" maxlength="32" placeholder="选填，如广东" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="城市" prop="city">
                  <el-input v-model="companyForm.city" maxlength="32" placeholder="选填" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-button class="submit-btn" type="primary" :loading="loading" @click="handleRegister">注册</el-button>
      <div class="auth-switch">
        已有账号？
        <router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { registerCompany, registerStudent } from '@/api/auth'
import { CREDIT_CODE_MESSAGE, isValidCreditCode } from '@/utils/creditCode'

const router = useRouter()
const activeTab = ref('student')
const loading = ref(false)
const studentFormRef = ref()
const companyFormRef = ref()

const usernameRule = [
  { required: true, message: '请输入用户名', trigger: 'blur' },
  { pattern: /^[A-Za-z][A-Za-z0-9_]{2,63}$/, message: '用户名需以字母开头，3-64 位字母、数字或下划线', trigger: 'blur' }
]
const passwordRule = [
  { required: true, message: '请输入密码', trigger: 'blur' },
  { min: 6, max: 32, message: '密码长度需为 6-32 位', trigger: 'blur' }
]

function confirmRule(getPassword) {
  return (_rule, value, callback) => {
    if (!value) {
      callback(new Error('请再次输入密码'))
      return
    }
    if (value !== getPassword()) {
      callback(new Error('两次输入的密码不一致'))
      return
    }
    callback()
  }
}

function optionalPhone(_rule, value, callback) {
  if (!value) {
    callback()
    return
  }
  if (!/^1\d{10}$/.test(value)) {
    callback(new Error('请输入 11 位手机号'))
    return
  }
  callback()
}

function optionalEmail(_rule, value, callback) {
  if (!value) {
    callback()
    return
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    callback(new Error('邮箱格式不正确'))
    return
  }
  callback()
}

const educationOptions = [
  { value: 1, label: '专科' },
  { value: 2, label: '本科' },
  { value: 3, label: '硕士' },
  { value: 4, label: '博士' }
]
const genderOptions = [
  { value: 0, label: '未知' },
  { value: 1, label: '男' },
  { value: 2, label: '女' }
]

const studentForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
  realName: '',
  gender: 0,
  education: 2,
  graduationYear: 2026,
  phone: '',
  email: '',
  school: '',
  college: '',
  major: '',
  studentNo: ''
})

const companyForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  companyName: '',
  shortName: '',
  creditCode: '',
  contactName: '',
  contactPhone: '',
  contactEmail: '',
  industry: '',
  province: '',
  city: ''
})

const studentRules = {
  username: usernameRule,
  password: passwordRule,
  confirmPassword: [{ required: true, validator: confirmRule(() => studentForm.password), trigger: 'blur' }],
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  realName: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  education: [{ required: true, message: '请选择学历', trigger: 'change' }],
  graduationYear: [{ required: true, message: '请填写毕业年份', trigger: 'change' }],
  phone: [{ validator: optionalPhone, trigger: 'blur' }],
  email: [{ validator: optionalEmail, trigger: 'blur' }]
}

const companyRules = {
  username: usernameRule,
  password: passwordRule,
  confirmPassword: [{ required: true, validator: confirmRule(() => companyForm.password), trigger: 'blur' }],
  companyName: [{ required: true, message: '请输入企业全称', trigger: 'blur' }],
  creditCode: [
    { required: true, message: '请输入统一社会信用代码', trigger: 'blur' },
    {
      validator: (_r, v, cb) => (isValidCreditCode(v)
        ? cb()
        : cb(new Error(CREDIT_CODE_MESSAGE))),
      trigger: 'blur'
    }
  ],
  contactName: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contactPhone: [{ validator: optionalPhone, trigger: 'blur' }],
  contactEmail: [{ validator: optionalEmail, trigger: 'blur' }]
}

function omitConfirm(form) {
  const payload = { ...form }
  delete payload.confirmPassword
  return payload
}

const handleRegister = async () => {
  const isStudent = activeTab.value === 'student'
  const formRef = isStudent ? studentFormRef.value : companyFormRef.value
  const valid = await formRef.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    if (isStudent) {
      await registerStudent(omitConfirm(studentForm))
      ElMessage.success('学生注册成功，请登录')
    } else {
      await registerCompany({ ...omitConfirm(companyForm), creditCode: companyForm.creditCode.trim().toUpperCase() })
      ElMessage.success('企业注册成功，请登录。资质审核通过前仅可维护企业资料')
    }
    router.push('/login')
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
  width: 760px;
  max-width: 100%;
  max-height: calc(100vh - 48px);
  overflow: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 28px 28px 20px;
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
  margin: 8px 0 12px;
  color: #718096;
  font-size: 14px;
}
.submit-btn {
  width: 100%;
  margin-top: 8px;
}
.auth-switch {
  margin-top: 14px;
  text-align: center;
  color: #4a5568;
  font-size: 14px;
}
.auth-switch a {
  color: #409eff;
  text-decoration: none;
}
</style>
