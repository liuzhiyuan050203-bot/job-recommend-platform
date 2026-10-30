<template>
  <div class="home-container">
    <div class="top-bar">
      <div class="brand" @click="router.push('/')">高校就业推荐平台</div>
      <div class="top-actions">
        <template v-if="userStore.isLoggedIn">
          <span class="welcome">你好，{{ userStore.nickname }}</span>
          <el-button type="primary" @click="goWorkspace">进入工作台</el-button>
          <el-button @click="handleLogout">退出</el-button>
        </template>
        <template v-else>
          <el-button @click="router.push('/login')">登录</el-button>
          <el-button type="primary" @click="router.push('/register')">注册</el-button>
        </template>
      </div>
    </div>
    <!-- 顶部主横幅 -->
    <header class="hero-section">
      <div class="hero-badge">毕业设计 · 2026届</div>
      <h1 class="hero-title">基于 Spark 与 RAG 的高校就业推荐平台</h1>
      <p class="hero-subtitle">
        融合大数据离线挖掘 (PySpark + 协同过滤/内容匹配) 与大模型检索增强生成 (RAG + LangChain) 的一站式大学生就业服务平台
      </p>

      <!-- 后端健康状态指示器 -->
      <div class="health-card">
        <div class="health-header">
          <span class="health-label">
            <el-icon><Connection /></el-icon> 服务通信链路状态检测
          </span>
          <el-button
            size="small"
            type="primary"
            plain
            :loading="healthLoading"
            icon="Refresh"
            @click="checkBackendHealth"
          >
            重新检测
          </el-button>
        </div>

        <div class="health-tags">
          <!-- 总体服务状态 -->
          <div class="status-item">
            <span class="item-name">后端主服务 (8080):</span>
            <el-tag :type="healthStatus.serverOk ? 'success' : 'danger'" effect="dark">
              {{ healthStatus.serverOk ? '运行正常 (Connected)' : '连接失败 (Disconnected)' }}
            </el-tag>
          </div>

          <!-- 数据库状态 (db 字段) -->
          <div class="status-item">
            <span class="item-name">数据库 (db):</span>
            <el-tag :type="healthStatus.dbOk ? 'success' : 'warning'" effect="light">
              {{ healthStatus.db }}
            </el-tag>
          </div>

          <!-- AI / RAG 智能体服务状态 (aiService 字段) -->
          <div class="status-item">
            <span class="item-name">AI智能体服务 (aiService):</span>
            <el-tag :type="healthStatus.aiOk ? 'success' : 'info'" effect="light">
              {{ healthStatus.aiService }}
            </el-tag>
          </div>
        </div>

        <div v-if="healthError" class="health-tip">
          <el-text type="info" size="small">
            * 提示：若后端尚未启动，可启动 Spring Boot (8080) 与 FastAPI (8000) 即可刷新连接。
          </el-text>
        </div>
      </div>
    </header>

    <!-- 三端入口快捷导航 -->
    <section class="portals-section">
      <h2 class="section-title">系统多端协同入口</h2>
      <el-row :gutter="24">
        <!-- 学生端 -->
        <el-col :xs="24" :sm="8">
          <el-card class="portal-card student-card" shadow="hover">
            <div class="card-icon student-icon">
              <el-icon><User /></el-icon>
            </div>
            <h3>学生门户</h3>
            <p>职位多维检索、个性化雷达图、简历在线构建与 User-CF / 内容智能匹配推荐。</p>
            <div class="card-action">
              <el-button type="primary" size="large" @click="navigateTo('/student')">
                进入学生端
                <el-icon class="el-icon--right"><Right /></el-icon>
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 企业端 -->
        <el-col :xs="24" :sm="8">
          <el-card class="portal-card company-card" shadow="hover">
            <div class="card-icon company-icon">
              <el-icon><OfficeBuilding /></el-icon>
            </div>
            <h3>企业门户</h3>
            <p>招聘岗位发布、初筛/面试状态机流转、面试日程提醒、招聘转化漏斗分析。</p>
            <div class="card-action">
              <el-button type="success" size="large" @click="navigateTo('/company')">
                进入企业端
                <el-icon class="el-icon--right"><Right /></el-icon>
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 管理员端 -->
        <el-col :xs="24" :sm="8">
          <el-card class="portal-card admin-card" shadow="hover">
            <div class="card-icon admin-icon">
              <el-icon><Setting /></el-icon>
            </div>
            <h3>管理员门户</h3>
            <p>资质审核认证、双选会政策管理、面经评论审核、Spark 统计就业数据大屏。</p>
            <div class="card-action">
              <el-button type="danger" size="large" @click="navigateTo('/admin')">
                进入管理端
                <el-icon class="el-icon--right"><Right /></el-icon>
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <!-- 演示 ECharts 图表展示 -->
    <section class="chart-section">
      <el-card shadow="never" class="chart-card">
        <template #header>
          <div class="chart-header">
            <div>
              <span class="chart-title">2026届热门技术岗位起薪与中位数 (Spark 离线聚合样例)</span>
              <span class="chart-desc">基于 EChart.vue 响应式通用组件封装</span>
            </div>
            <el-tag type="success" effect="plain">静态演示数据</el-tag>
          </div>
        </template>
        <EChart :option="salaryBarChartOption" height="380px" />
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getHealth } from '@/api/health'
import EChart from '@/components/EChart.vue'
import { useUserStore } from '@/stores/user'
import { roleHome } from '@/utils/role'

const router = useRouter()
const userStore = useUserStore()

const goWorkspace = () => {
  const user = userStore.userInfo
  if (user?.roleName === 'company' && Number(user.companyAuditStatus) !== 1) {
    router.push('/company/profile')
    return
  }
  router.push(roleHome(userStore.roleName))
}

const handleLogout = () => {
  userStore.logout()
  ElMessage.success('已退出登录')
}

const healthLoading = ref(false)
const healthError = ref(false)
const healthStatus = ref({
  serverOk: false,
  dbOk: false,
  db: '检测中...',
  aiOk: false,
  aiService: '检测中...'
})

// 检查后端健康状态
const checkBackendHealth = async () => {
  healthLoading.value = true
  healthError.value = false
  try {
    const res = await getHealth()
    healthStatus.value = {
      serverOk: true,
      dbOk: res?.db === 'connected' || res?.db === 'ok' || res?.db === 'UP',
      db: res?.db || 'connected',
      aiOk: res?.aiService === 'connected' || res?.aiService === 'ok' || res?.aiService === 'UP',
      aiService: res?.aiService || 'connected'
    }
  } catch (err) {
    healthError.value = true
    healthStatus.value = {
      serverOk: false,
      dbOk: false,
      db: '未连接 (Offline)',
      aiOk: false,
      aiService: '未连接 (Offline)'
    }
  } finally {
    healthLoading.value = false
  }
}

const navigateTo = (path) => {
  if (!userStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: path } })
    return
  }
  router.push(path)
}

// 热门技术岗位薪资演示柱状图
const salaryBarChartOption = computed(() => {
  const categories = [
    '大数据开发 (Spark)',
    'AI / RAG 算法',
    'Java 后端开发',
    'Go 云原生开发',
    'Vue / 前端工程',
    '数据分析师',
    '测试开发'
  ]
  const avgSalaries = [18.5, 23.2, 16.8, 17.5, 14.2, 13.8, 12.5]
  const medianSalaries = [17.0, 21.0, 15.5, 16.0, 13.5, 12.8, 11.8]

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params) => {
        let text = `<strong>${params[0].name}</strong><br/>`
        params.forEach((item) => {
          text += `${item.marker} ${item.seriesName}: <b>${item.value} k/月</b><br/>`
        })
        return text
      }
    },
    legend: {
      data: ['平均薪资 (k/月)', '薪资中位数 (k/月)'],
      top: 'top'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: [
      {
        type: 'category',
        data: categories,
        axisTick: {
          alignWithLabel: true
        },
        axisLabel: {
          interval: 0,
          rotate: 15
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: '薪资 (k/月)',
        min: 0,
        max: 28,
        axisLabel: {
          formatter: '{value} k'
        }
      }
    ],
    series: [
      {
        name: '平均薪资 (k/月)',
        type: 'bar',
        barWidth: '28%',
        itemStyle: {
          color: '#409eff',
          borderRadius: [4, 4, 0, 0]
        },
        data: avgSalaries
      },
      {
        name: '薪资中位数 (k/月)',
        type: 'bar',
        barWidth: '28%',
        itemStyle: {
          color: '#67c23a',
          borderRadius: [4, 4, 0, 0]
        },
        data: medianSalaries
      }
    ]
  }
})

onMounted(() => {
  checkBackendHealth()
})
</script>

<style scoped>
.home-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.brand {
  font-size: 18px;
  font-weight: 700;
  color: #1a202c;
  cursor: pointer;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.welcome {
  color: #4a5568;
  font-size: 14px;
}

.hero-section {
  text-align: center;
  margin-bottom: 36px;
}

.hero-badge {
  display: inline-block;
  padding: 4px 12px;
  background-color: #ecf5ff;
  color: #409eff;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 12px;
}

.hero-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 12px 0;
}

.hero-subtitle {
  font-size: 15px;
  color: #718096;
  max-width: 800px;
  margin: 0 auto 28px;
  line-height: 1.6;
}

.health-card {
  max-width: 760px;
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px dashed #e2e8f0;
  padding-bottom: 10px;
  margin-bottom: 12px;
}

.health-label {
  font-size: 14px;
  font-weight: 600;
  color: #2d3748;
  display: flex;
  align-items: center;
  gap: 6px;
}

.health-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-around;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.item-name {
  color: #4a5568;
}

.health-tip {
  margin-top: 10px;
  text-align: left;
}

.portals-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin-bottom: 20px;
  text-align: center;
}

.portal-card {
  text-align: center;
  padding: 10px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.25s ease;
  border-radius: 12px;
}

.portal-card:hover {
  transform: translateY(-4px);
}

.card-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin: 10px auto 16px;
}

.student-icon {
  background-color: #ecf5ff;
  color: #409eff;
}

.company-icon {
  background-color: #f0f9eb;
  color: #67c23a;
}

.admin-icon {
  background-color: #fef0f0;
  color: #f56c6c;
}

.portal-card h3 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #2d3748;
}

.portal-card p {
  font-size: 13px;
  color: #718096;
  line-height: 1.5;
  margin-bottom: 20px;
  min-height: 40px;
}

.card-action {
  margin-top: auto;
}

.chart-section {
  margin-bottom: 20px;
}

.chart-card {
  border-radius: 12px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: #2d3748;
  margin-right: 12px;
}

.chart-desc {
  font-size: 12px;
  color: #a0aec0;
}
</style>
