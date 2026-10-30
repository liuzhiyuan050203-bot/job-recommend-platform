<template>
  <div class="community-page-container">
    <div class="header-bar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">面经与企业评价社区</span>
        </template>
        <template #extra>
          <el-button v-if="userStore.isLoggedIn && userStore.roleName === 'student'" type="primary" icon="Edit" @click="router.push('/student/community')">
            去我的发帖 / 撰写面经
          </el-button>
          <el-button @click="router.push('/')">返回首页</el-button>
        </template>
      </el-page-header>
    </div>

    <!-- 筛选卡片 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-wrapper">
        <el-radio-group v-model="selectedType" size="large" @change="handleTypeChange">
          <el-radio-button :value="0">全部动态</el-radio-button>
          <el-radio-button :value="1">校招面经</el-radio-button>
          <el-radio-button :value="2">企业真实评价</el-radio-button>
        </el-radio-group>

        <div class="search-box">
          <el-input
            v-model="keyword"
            placeholder="搜索面经标题、企业或岗位..."
            clearable
            style="width: 300px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #append>
              <el-button icon="Search" @click="handleSearch" />
            </template>
          </el-input>
        </div>
      </div>
    </el-card>

    <!-- 帖子列表 -->
    <el-card shadow="never" class="list-card" v-loading="loading">
      <div v-if="posts.length === 0" class="empty-state">
        <el-empty description="暂无相关面经或评价分享" />
      </div>

      <div v-else class="post-grid">
        <el-card
          v-for="item in posts"
          :key="item.id"
          class="post-card"
          shadow="hover"
          @click="viewPost(item.id)"
        >
          <div class="post-header">
            <el-tag :type="item.postType === 1 ? 'success' : 'warning'" size="small">
              {{ item.postTypeName }}
            </el-tag>
            <span v-if="item.companyName" class="company-badge">
              <el-icon><OfficeBuilding /></el-icon> {{ item.companyName }}
            </span>
            <span v-if="item.positionTitle" class="pos-badge">
              <el-icon><Briefcase /></el-icon> {{ item.positionTitle }}
            </span>
            <el-rate
              v-if="item.postType === 2 && item.rating"
              v-model="item.rating"
              disabled
              size="small"
              class="rate-stars"
            />
          </div>

          <h3 class="post-title">{{ item.title }}</h3>
          <p class="post-excerpt">{{ item.content }}</p>

          <div class="post-footer">
            <div class="author-info">
              <el-avatar :size="24" :src="item.authorAvatar" icon="UserFilled" />
              <span class="author-name">{{ item.authorName }}</span>
            </div>
            <div class="meta-info">
              <span><el-icon><ChatDotRound /></el-icon> {{ item.commentCount || 0 }} 评论</span>
              <span><el-icon><Calendar /></el-icon> {{ item.createTime.substring(0, 10) }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 分页组件 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[6, 12, 24]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchPosts"
          @current-change="fetchPosts"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { getPosts } from '@/api/public'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const selectedType = ref(0)
const keyword = ref('')
const posts = ref([])

const pagination = reactive({
  current: 1,
  size: 12,
  total: 0
})

const fetchPosts = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      keyword: keyword.value.trim() || undefined
    }
    if (selectedType.value > 0) {
      params.postType = selectedType.value
    }
    const res = await getPosts(params)
    posts.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleTypeChange = () => {
  pagination.current = 1
  fetchPosts()
}

const handleSearch = () => {
  pagination.current = 1
  fetchPosts()
}

const viewPost = (id) => {
  router.push(`/community/${id}`)
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  fetchPosts()
})
</script>

<style scoped>
.community-page-container {
  max-width: 1100px;
  margin: 24px auto;
  padding: 0 16px;
}
.header-bar {
  margin-bottom: 20px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
.filter-card {
  margin-bottom: 16px;
  border-radius: 8px;
}
.filter-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.list-card {
  border-radius: 8px;
  min-height: 480px;
}
.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.post-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}
.post-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--el-box-shadow-light);
}
.post-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.company-badge, .pos-badge {
  font-size: 12px;
  color: var(--el-text-color-regular);
  background-color: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.rate-stars {
  margin-left: auto;
}
.post-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.post-excerpt {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  margin: 0 0 14px;
  height: 40px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.post-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.author-info {
  display: flex;
  align-items: center;
  gap: 6px;
}
.author-name {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.meta-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.meta-info span {
  display: flex;
  align-items: center;
  gap: 3px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
