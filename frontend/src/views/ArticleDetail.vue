<template>
  <div class="article-detail-container" v-loading="loading">
    <div class="header-bar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">文章详情</span>
        </template>
        <template #extra>
          <el-button @click="router.push('/articles')">全部文章</el-button>
          <el-button type="primary" plain @click="router.push('/')">平台首页</el-button>
        </template>
      </el-page-header>
    </div>

    <el-card shadow="never" class="content-card" v-if="article">
      <div class="article-header">
        <div class="tag-row">
          <el-tag :type="getTypeTagType(article.articleType)" size="default">
            {{ article.articleTypeName }}
          </el-tag>
          <el-tag v-if="article.topFlag === 1" type="danger" effect="dark" size="default">
            置顶公告
          </el-tag>
        </div>
        <h1 class="main-title">{{ article.title }}</h1>
        <div class="meta-bar">
          <span><el-icon><User /></el-icon> 发布人：{{ article.publisherName || '高校就业指导中心' }}</span>
          <span><el-icon><Calendar /></el-icon> 发布时间：{{ article.publishTime || article.createTime }}</span>
          <span><el-icon><View /></el-icon> 浏览量：{{ article.viewCount }} 次</span>
        </div>
      </div>

      <el-alert
        v-if="article.summary"
        :title="article.summary"
        type="info"
        :closable="false"
        show-icon
        class="summary-alert"
      />

      <div class="article-body">
        <div class="article-content" v-html="formattedContent"></div>
      </div>

      <div class="footer-actions">
        <el-button icon="Back" @click="goBack">返回上一页</el-button>
      </div>
    </el-card>

    <el-card v-else-if="!loading" shadow="never" class="content-card">
      <el-empty description="未找到文章内容或已被撤回" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getArticle } from '@/api/public'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const article = ref(null)

const getTypeTagType = (type) => {
  if (type === 1) return 'success'
  if (type === 2) return 'primary'
  return 'warning'
}

const formattedContent = computed(() => {
  if (!article.value?.content) return ''
  // 简单换行转换为段落展示
  return article.value.content
    .split('\n')
    .filter(p => p.trim())
    .map(p => `<p>${p}</p>`)
    .join('')
})

const fetchDetail = async () => {
  const id = route.params.id
  if (!id) return
  loading.value = true
  try {
    article.value = await getArticle(id)
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/articles')
  }
}

onMounted(() => {
  fetchDetail()
})
</script>

<style scoped>
.article-detail-container {
  max-width: 960px;
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
.content-card {
  border-radius: 8px;
  padding: 24px;
  min-height: 500px;
}
.article-header {
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 20px;
  margin-bottom: 20px;
  text-align: center;
}
.tag-row {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}
.main-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.4;
  margin: 0 0 16px;
}
.meta-bar {
  display: flex;
  justify-content: center;
  gap: 24px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.meta-bar span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.summary-alert {
  margin-bottom: 24px;
}
.article-body {
  font-size: 16px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
  min-height: 260px;
}
.article-content :deep(p) {
  margin-bottom: 16px;
  text-indent: 2em;
}
.footer-actions {
  display: flex;
  justify-content: center;
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px dashed var(--el-border-color);
}
</style>
