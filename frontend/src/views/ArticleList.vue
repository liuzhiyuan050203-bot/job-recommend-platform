<template>
  <div class="article-page-container">
    <div class="header-bar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">{{ pageTitle }}</span>
        </template>
        <template #extra>
          <el-button @click="router.push('/')">返回平台首页</el-button>
        </template>
      </el-page-header>
    </div>

    <!-- 分类标签与搜索区 -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-wrapper">
        <el-radio-group v-model="selectedType" size="large" @change="handleTypeChange">
          <el-radio-button :value="0">全部资讯</el-radio-button>
          <el-radio-button :value="1">双选会公告</el-radio-button>
          <el-radio-button :value="2">就业政策</el-radio-button>
          <el-radio-button :value="3">面试指南 / 资讯</el-radio-button>
        </el-radio-group>

        <div class="search-box">
          <el-input
            v-model="keyword"
            placeholder="搜索文章标题或摘要..."
            clearable
            style="width: 280px"
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

    <!-- 文章列表 -->
    <el-card shadow="never" class="list-card" v-loading="loading">
      <div v-if="articles.length === 0" class="empty-state">
        <el-empty description="暂无相关文章资讯" />
      </div>

      <div v-else class="article-list">
        <div
          v-for="item in articles"
          :key="item.id"
          class="article-item"
          @click="viewDetail(item.id)"
        >
          <div class="article-info">
            <div class="title-row">
              <el-tag v-if="item.topFlag === 1" type="danger" effect="dark" size="small" class="tag">置顶</el-tag>
              <el-tag :type="getTypeTagType(item.articleType)" size="small" class="tag">
                {{ item.articleTypeName }}
              </el-tag>
              <span class="article-title">{{ item.title }}</span>
            </div>
            <p class="article-summary">{{ item.summary || '暂无摘要' }}</p>
            <div class="meta-row">
              <span class="meta-item"><el-icon><User /></el-icon> {{ item.publisherName || '高校就业指导中心' }}</span>
              <span class="meta-item"><el-icon><Calendar /></el-icon> {{ item.publishTime ? item.publishTime.substring(0, 10) : item.createTime.substring(0, 10) }}</span>
              <span class="meta-item"><el-icon><View /></el-icon> {{ item.viewCount }} 次阅读</span>
            </div>
          </div>
          <div v-if="item.coverUrl" class="article-cover">
            <img :src="item.coverUrl" alt="cover" />
          </div>
        </div>
      </div>

      <!-- 分页组件 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[5, 10, 20]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchArticles"
          @current-change="fetchArticles"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getArticles } from '@/api/public'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const selectedType = ref(0)
const keyword = ref('')
const articles = ref([])

const pagination = reactive({
  current: 1,
  size: 10,
  total: 0
})

const pageTitle = computed(() => {
  if (selectedType.value === 1) return '双选会公告'
  if (selectedType.value === 2) return '就业政策解读'
  if (selectedType.value === 3) return '面试指南与就业资讯'
  return '校园就业资讯与政策公告'
})

const getTypeTagType = (type) => {
  if (type === 1) return 'success'
  if (type === 2) return 'primary'
  return 'warning'
}

const fetchArticles = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      keyword: keyword.value.trim() || undefined
    }
    if (selectedType.value > 0) {
      params.type = selectedType.value
    }
    const res = await getArticles(params)
    articles.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleTypeChange = () => {
  pagination.current = 1
  fetchArticles()
}

const handleSearch = () => {
  pagination.current = 1
  fetchArticles()
}

const viewDetail = (id) => {
  router.push(`/articles/${id}`)
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  if (route.query.type) {
    selectedType.value = Number(route.query.type)
  }
  fetchArticles()
})
</script>

<style scoped>
.article-page-container {
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
.article-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: background-color 0.2s;
}
.article-item:hover {
  background-color: var(--el-fill-color-light);
}
.article-info {
  flex: 1;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.tag {
  flex-shrink: 0;
}
.article-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.article-title:hover {
  color: var(--el-color-primary);
}
.article-summary {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  margin: 0 0 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.meta-row {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.article-cover img {
  width: 140px;
  height: 90px;
  object-fit: cover;
  border-radius: 6px;
  margin-left: 16px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
