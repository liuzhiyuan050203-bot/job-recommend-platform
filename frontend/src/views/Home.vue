<template>
  <div class="home-container">
    <!-- 顶部状态与导航条 -->
    <div class="top-bar">
      <div class="brand" @click="router.push('/')">高校就业推荐平台</div>
      <div class="top-nav-links">
        <el-button link @click="router.push('/articles')">就业资讯与公告</el-button>
        <el-button link @click="router.push('/community')">求职面经社区</el-button>
      </div>
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

    <!-- 首页轮播图 -->
    <section v-if="banners.length > 0" class="banner-section">
      <el-carousel :interval="4000" type="card" height="240px">
        <el-carousel-item v-for="item in banners" :key="item.id" @click="handleBannerClick(item)">
          <div class="carousel-card">
            <el-image :src="item.imageUrl" fit="cover" class="carousel-img" />
            <div class="carousel-title-mask">
              <span>{{ item.title }}</span>
            </div>
          </div>
        </el-carousel-item>
      </el-carousel>
    </section>

    <!-- 顶部主标题与健康状态 -->
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
          <div class="status-item">
            <span class="item-name">后端主服务 (8080):</span>
            <el-tag :type="healthStatus.serverOk ? 'success' : 'danger'" effect="dark">
              {{ healthStatus.serverOk ? '运行正常 (Connected)' : '连接失败 (Disconnected)' }}
            </el-tag>
          </div>
          <div class="status-item">
            <span class="item-name">数据库 (db):</span>
            <el-tag :type="healthStatus.dbOk ? 'success' : 'warning'" effect="light">
              {{ healthStatus.db }}
            </el-tag>
          </div>
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

    <!-- 三栏文章资讯区 (双选会公告 / 就业政策 / 面试指南) -->
    <section class="articles-columns-section">
      <div class="section-header">
        <h2 class="section-title">校园资讯与就业政策专栏</h2>
        <el-button link type="primary" @click="router.push('/articles')">
          查看全部资讯 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <el-row :gutter="20">
        <!-- 栏目 1：双选会公告 -->
        <el-col :xs="24" :md="8">
          <el-card shadow="hover" class="column-card">
            <template #header>
              <div class="column-header">
                <span class="col-title success-col"><el-icon><Calendar /></el-icon> 双选会公告</span>
                <el-button link size="small" @click="router.push('/articles?type=1')">更多</el-button>
              </div>
            </template>
            <div v-if="fairsList.length === 0" class="empty-col">暂无最新公告</div>
            <ul v-else class="article-mini-list">
              <li v-for="a in fairsList" :key="a.id" @click="router.push(`/articles/${a.id}`)">
                <span class="mini-title">{{ a.title }}</span>
                <span class="mini-date">{{ a.publishTime ? a.publishTime.substring(5, 10) : a.createTime.substring(5, 10) }}</span>
              </li>
            </ul>
          </el-card>
        </el-col>

        <!-- 栏目 2：就业政策 -->
        <el-col :xs="24" :md="8">
          <el-card shadow="hover" class="column-card">
            <template #header>
              <div class="column-header">
                <span class="col-title primary-col"><el-icon><Document /></el-icon> 就业政策解读</span>
                <el-button link size="small" @click="router.push('/articles?type=2')">更多</el-button>
              </div>
            </template>
            <div v-if="policyList.length === 0" class="empty-col">暂无最新政策</div>
            <ul v-else class="article-mini-list">
              <li v-for="a in policyList" :key="a.id" @click="router.push(`/articles/${a.id}`)">
                <span class="mini-title">{{ a.title }}</span>
                <span class="mini-date">{{ a.publishTime ? a.publishTime.substring(5, 10) : a.createTime.substring(5, 10) }}</span>
              </li>
            </ul>
          </el-card>
        </el-col>

        <!-- 栏目 3：面试指南与资讯 -->
        <el-col :xs="24" :md="8">
          <el-card shadow="hover" class="column-card">
            <template #header>
              <div class="column-header">
                <span class="col-title warning-col"><el-icon><Guide /></el-icon> 面试指南与资讯</span>
                <el-button link size="small" @click="router.push('/articles?type=3')">更多</el-button>
              </div>
            </template>
            <div v-if="newsList.length === 0" class="empty-col">暂无指南资讯</div>
            <ul v-else class="article-mini-list">
              <li v-for="a in newsList" :key="a.id" @click="router.push(`/articles/${a.id}`)">
                <span class="mini-title">{{ a.title }}</span>
                <span class="mini-date">{{ a.publishTime ? a.publishTime.substring(5, 10) : a.createTime.substring(5, 10) }}</span>
              </li>
            </ul>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <!-- 最新求职面经与企业评价 -->
    <section class="community-preview-section">
      <div class="section-header">
        <h2 class="section-title">最新校招面经与企业评价</h2>
        <el-button link type="primary" @click="router.push('/community')">
          进入社区互动广场 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <el-row :gutter="20">
        <el-col v-for="p in latestPosts" :key="p.id" :xs="24" :sm="12" :md="6">
          <el-card shadow="hover" class="home-post-card" @click="router.push(`/community/${p.id}`)">
            <div class="hp-top">
              <el-tag :type="p.postType === 1 ? 'success' : 'warning'" size="small">
                {{ p.postTypeName }}
              </el-tag>
              <span v-if="p.companyName" class="hp-company">{{ p.companyName }}</span>
            </div>
            <h4 class="hp-title">{{ p.title }}</h4>
            <p class="hp-content">{{ p.content }}</p>
            <div class="hp-footer">
              <span class="hp-author">{{ p.authorName }}</span>
              <span class="hp-comments"><el-icon><ChatDotRound /></el-icon> {{ p.commentCount }}</span>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>

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
            <p>维护个人档案与技能、简历在线构建、面经社区互动、雷达图与推荐职位。</p>
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
            <p>完善企业基本资料、营业执照资质认证、岗位招聘发布与初筛/面试流转。</p>
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
            <p>企业资质审核、职位合规审核、面经评论内容审查、轮播与文章资讯配置。</p>
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

    <section class="chart-section">
      <div class="section-header">
        <h2 class="section-title">就业市场数据看板</h2>
      </div>
      <el-skeleton :loading="statsLoading" animated>
        <template #template>
          <el-skeleton-item variant="rect" style="height: 88px; margin-bottom: 16px" />
          <el-skeleton-item variant="rect" style="height: 320px" />
        </template>
        <el-row :gutter="16" class="overview-row">
          <el-col v-for="item in overviewCards" :key="item.label" :xs="12" :sm="6">
            <el-card shadow="hover" class="overview-card">
              <div class="overview-label">{{ item.label }}</div>
              <div class="overview-value">{{ item.value }}</div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><span class="chart-title">技术方向薪资（P25 / 中位数 / P75）</span></template>
              <el-empty v-if="!directionRows.length" description="暂无薪资统计" />
              <EChart v-else :option="directionOption" height="360px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><span class="chart-title">城市平均月薪</span></template>
              <el-empty v-if="!cityRows.length" description="暂无城市薪资" />
              <EChart v-else :option="cityOption" height="360px" />
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="16" class="chart-gap">
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><span class="chart-title">技术需求趋势</span></template>
              <el-empty v-if="!(trend.months || []).length" description="暂无技术趋势" />
              <EChart v-else :option="trendOption" height="360px" />
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="chart-card">
              <template #header><span class="chart-title">地区职位分布</span></template>
              <el-empty v-if="!region.length" description="暂无地区统计" />
              <EChart v-else :option="regionOption" height="360px" />
            </el-card>
          </el-col>
        </el-row>
        <el-card shadow="never" class="chart-card chart-gap">
          <template #header><span class="chart-title">近 12 个月招聘需求</span></template>
          <el-empty v-if="!(hiring.months || []).length" description="暂无招聘需求" />
          <EChart v-else :option="hiringOption" height="360px" />
        </el-card>
      </el-skeleton>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getHealth } from '@/api/health'
import {
  getBanners,
  getArticles,
  getPosts,
  getStatsOverview,
  getSalaryStats,
  getTechTrend,
  getRegionStats,
  getHiringDemand
} from '@/api/public'
import EChart from '@/components/EChart.vue'
import { useUserStore } from '@/stores/user'
import { roleHome } from '@/utils/role'

const router = useRouter()
const userStore = useUserStore()

const banners = ref([])
const fairsList = ref([])
const policyList = ref([])
const newsList = ref([])
const latestPosts = ref([])
const statsLoading = ref(true)
const overview = ref({})
const salary = ref({ byDirection: [], byCity: [] })
const trend = ref({ months: [], series: [] })
const region = ref([])
const hiring = ref({ months: [], jobCounts: [], applyCounts: [] })

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

const handleBannerClick = (item) => {
  if (item.linkUrl) {
    if (item.linkUrl.startsWith('http')) {
      window.open(item.linkUrl, '_blank')
    } else {
      router.push(item.linkUrl)
    }
  }
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

const fetchPublicHomeData = async () => {
  try {
    // 轮播图
    banners.value = (await getBanners()) || []

    // 双选会公告
    const fairs = await getArticles({ type: 1, current: 1, size: 5 })
    fairsList.value = fairs.records || []

    // 就业政策
    const policies = await getArticles({ type: 2, current: 1, size: 5 })
    policyList.value = policies.records || []

    // 面试指南
    const news = await getArticles({ type: 3, current: 1, size: 5 })
    newsList.value = news.records || []

    // 最新面经
    const postsRes = await getPosts({ current: 1, size: 4 })
    latestPosts.value = postsRes.records || []
  } catch (err) {
    console.error('加载公共内容失败:', err)
  }
}

const navigateTo = (path) => {
  if (!userStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: path } })
    return
  }
  router.push(path)
}

const directionRows = computed(() => (salary.value.byDirection || []).slice(0, 8))
const cityRows = computed(() => [...(salary.value.byCity || [])].slice(0, 10).reverse())

const overviewCards = computed(() => {
  const data = overview.value || {}
  return [
    { label: '在招职位', value: displayCount(data.jobCount) },
    { label: '入驻企业', value: displayCount(data.companyCount) },
    { label: '在校学生', value: displayCount(data.studentCount) },
    { label: '平台投递', value: displayCount(data.applicationCount) }
  ]
})

function displayCount(value) {
  return value === 0 || value ? value : '-'
}

function toK(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 0
  return Math.round((number / 1000) * 10) / 10
}

const directionOption = computed(() => {
  const rows = directionRows.value
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (value) => `${value} k/月` },
    legend: { top: 0 },
    grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((item) => item.techDirection),
      axisLabel: { interval: 0, rotate: 20 }
    },
    yAxis: { type: 'value', name: '千元/月' },
    series: [
      { name: 'P25', type: 'bar', data: rows.map((item) => toK(item.p25Salary)) },
      { name: '中位数', type: 'bar', data: rows.map((item) => toK(item.medianSalary || item.avgSalary)) },
      { name: 'P75', type: 'bar', data: rows.map((item) => toK(item.p75Salary)) }
    ]
  }
})

const cityOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (value) => `${value} k/月` },
  grid: { left: 12, right: 24, top: 16, bottom: 8, containLabel: true },
  xAxis: { type: 'value', name: '千元/月' },
  yAxis: { type: 'category', data: cityRows.value.map((item) => item.city) },
  series: [
    {
      name: '平均月薪',
      type: 'bar',
      data: cityRows.value.map((item) => toK(item.avgSalary)),
      itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] }
    }
  ]
}))

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { type: 'scroll', top: 0 },
  grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
  xAxis: { type: 'category', boundaryGap: false, data: trend.value.months || [] },
  yAxis: { type: 'value', name: '职位数' },
  series: (trend.value.series || []).map((item) => ({
    name: item.name,
    type: 'line',
    smooth: true,
    data: item.data || []
  }))
}))

const regionOption = computed(() => {
  const rows = [...region.value].slice(0, 12).reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 24, top: 16, bottom: 8, containLabel: true },
    xAxis: { type: 'value', name: '职位数' },
    yAxis: { type: 'category', data: rows.map((item) => item.name) },
    series: [
      {
        name: '职位数',
        type: 'bar',
        data: rows.map((item) => item.value || 0),
        itemStyle: { color: '#67c23a', borderRadius: [0, 4, 4, 0] }
      }
    ]
  }
})

const hiringOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 12, right: 16, top: 36, bottom: 8, containLabel: true },
  xAxis: { type: 'category', data: hiring.value.months || [] },
  yAxis: { type: 'value', name: '数量', minInterval: 1 },
  series: [
    { name: '发布职位', type: 'bar', data: hiring.value.jobCounts || [] },
    { name: '投递', type: 'line', smooth: true, data: hiring.value.applyCounts || [] }
  ]
}))

async function loadMarketStats() {
  statsLoading.value = true
  const tasks = await Promise.allSettled([
    getStatsOverview(),
    getSalaryStats(),
    getTechTrend({ top: 6, months: 12 }),
    getRegionStats(),
    getHiringDemand({ months: 12 })
  ])
  const pick = (index, fallback) => (tasks[index].status === 'fulfilled' ? tasks[index].value : fallback)
  overview.value = pick(0, {}) || {}
  salary.value = pick(1, { byDirection: [], byCity: [] }) || { byDirection: [], byCity: [] }
  trend.value = pick(2, { months: [], series: [] }) || { months: [], series: [] }
  region.value = pick(3, []) || []
  hiring.value = pick(4, { months: [], jobCounts: [], applyCounts: [] }) || { months: [], jobCounts: [], applyCounts: [] }
  statsLoading.value = false
}

onMounted(() => {
  checkBackendHealth()
  fetchPublicHomeData()
  loadMarketStats()
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
  margin-bottom: 24px;
}

.brand {
  font-size: 18px;
  font-weight: 700;
  color: #1a202c;
  cursor: pointer;
}

.top-nav-links {
  display: flex;
  gap: 16px;
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

.banner-section {
  margin-bottom: 30px;
}

.carousel-card {
  position: relative;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
}

.carousel-img {
  width: 100%;
  height: 100%;
}

.carousel-title-mask {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
  color: #ffffff;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 600;
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

.articles-columns-section, .community-preview-section {
  margin-bottom: 36px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.column-card {
  border-radius: 10px;
  height: 230px;
  display: flex;
  flex-direction: column;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.col-title {
  font-weight: 600;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.success-col { color: #67c23a; }
.primary-col { color: #409eff; }
.warning-col { color: #e6a23c; }

.empty-col {
  color: #a0aec0;
  font-size: 13px;
  text-align: center;
  margin-top: 40px;
}

.article-mini-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.article-mini-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  cursor: pointer;
  transition: color 0.15s;
}

.article-mini-list li:hover .mini-title {
  color: var(--el-color-primary);
}

.mini-title {
  font-size: 13px;
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 78%;
}

.mini-date {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.home-post-card {
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  height: 100%;
}

.home-post-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--el-box-shadow-light);
}

.hp-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.hp-company {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hp-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hp-content {
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  height: 36px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  margin: 0 0 10px;
}

.hp-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
}

.portals-section {
  margin-bottom: 40px;
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

.overview-row {
  margin-bottom: 16px;
}

.overview-card {
  margin-bottom: 12px;
}

.overview-label {
  color: #909399;
  font-size: 13px;
}

.overview-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: #2d3748;
}

.chart-gap {
  margin-top: 16px;
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
