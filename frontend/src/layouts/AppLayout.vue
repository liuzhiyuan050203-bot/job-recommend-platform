<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
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
        >
          <el-icon v-if="item.icon">
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主体区域 -->
    <el-container>
      <!-- 顶栏 -->
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
              <span class="username">{{ userStore.userInfo.name || roleName + '用户' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="home">返回主页</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

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
  }
})

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const currentMenuTitle = computed(() => {
  const match = props.menuItems.find((item) => item.path === route.path)
  return match ? match.title : '当前页面'
})

const handleUserCommand = (cmd) => {
  if (cmd === 'home') {
    router.push('/')
  } else if (cmd === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/')
  }
}
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
}

.layout-header {
  height: 60px;
  background-color: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
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
</style>
