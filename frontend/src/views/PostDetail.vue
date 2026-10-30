<template>
  <div class="post-detail-container" v-loading="loading">
    <div class="header-bar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">面经详情与交流互动</span>
        </template>
        <template #extra>
          <el-button @click="router.push('/community')">社区广场</el-button>
          <el-button type="primary" plain @click="router.push('/')">平台首页</el-button>
        </template>
      </el-page-header>
    </div>

    <el-card shadow="never" class="post-card" v-if="post">
      <!-- 帖子头部元信息 -->
      <div class="post-header">
        <div class="post-tags">
          <el-tag :type="post.postType === 1 ? 'success' : 'warning'" size="default">
            {{ post.postTypeName }}
          </el-tag>
          <el-tag v-if="post.companyName" type="info" size="default">
            <el-icon><OfficeBuilding /></el-icon> {{ post.companyName }}
          </el-tag>
          <el-tag v-if="post.positionTitle" type="info" effect="plain" size="default">
            <el-icon><Briefcase /></el-icon> {{ post.positionTitle }}
          </el-tag>
        </div>

        <h1 class="post-title">{{ post.title }}</h1>

        <div class="author-bar">
          <div class="author-left">
            <el-avatar :size="36" :src="post.authorAvatar" icon="UserFilled" />
            <div class="author-meta">
              <span class="name">{{ post.authorName }}</span>
              <span class="date">发布于 {{ post.createTime }}</span>
            </div>
          </div>
          <div v-if="post.postType === 2 && post.rating" class="rating-box">
            <span class="rating-label">企业综合评价星级：</span>
            <el-rate v-model="post.rating" disabled show-score text-color="#ff9900" />
          </div>
        </div>
      </div>

      <!-- 正文内容 -->
      <div class="post-body">
        <div class="post-content" v-html="formattedContent"></div>
      </div>

      <!-- 评论区域 -->
      <div class="comment-section">
        <div class="comment-header">
          <h3>交流与评论 ({{ post.comments?.length || 0 }})</h3>
        </div>

        <!-- 发送评论输入框（学生登录） -->
        <div v-if="userStore.isLoggedIn && userStore.roleName === 'student'" class="comment-input-box">
          <el-input
            v-model="newComment"
            type="textarea"
            :rows="3"
            placeholder="写下你的疑问、面试体会或感谢分享（提交后将进入审核流）..."
            maxlength="500"
            show-word-limit
          />
          <div class="comment-btn-row">
            <el-button type="primary" :loading="submittingComment" @click="handleSubmitComment">
              发表评论
            </el-button>
          </div>
        </div>
        <div v-else-if="!userStore.isLoggedIn" class="comment-login-tip">
          <el-text type="info">登录学生账号后可参与面经互动与提问交流。</el-text>
          <el-button type="primary" link @click="router.push('/login')">立即登录</el-button>
        </div>

        <!-- 评论列表 -->
        <div v-if="post.comments && post.comments.length > 0" class="comment-list">
          <div v-for="item in post.comments" :key="item.id" class="comment-item">
            <el-avatar :size="32" :src="item.authorAvatar" icon="UserFilled" />
            <div class="comment-content-wrap">
              <div class="comment-user-row">
                <span class="comment-user">{{ item.authorName }}</span>
                <span class="comment-time">{{ item.createTime }}</span>
                <el-button
                  v-if="userStore.isLoggedIn && userStore.userId === item.userId"
                  type="danger"
                  link
                  size="small"
                  @click="handleDeleteComment(item.id)"
                >
                  删除
                </el-button>
              </div>
              <p class="comment-text">{{ item.content }}</p>
            </div>
          </div>
        </div>
        <div v-else class="no-comment">
          <el-empty description="暂无评论，快来抢沙发吧" :image-size="80" />
        </div>
      </div>
    </el-card>

    <el-card v-else-if="!loading" shadow="never" class="post-card">
      <el-empty description="未找到帖子或尚未通过审核" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getPost } from '@/api/public'
import { addComment, deleteComment } from '@/api/student'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const submittingComment = ref(false)
const post = ref(null)
const newComment = ref('')

const formattedContent = computed(() => {
  if (!post.value?.content) return ''
  return post.value.content
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
    post.value = await getPost(id)
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSubmitComment = async () => {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  submittingComment.value = true
  try {
    await addComment(post.value.id, { content: newComment.value.trim() })
    ElMessage.success('评论提交成功，审核通过后将公开展示')
    newComment.value = ''
    fetchDetail()
  } catch (err) {
    console.error(err)
  } finally {
    submittingComment.value = false
  }
}

const handleDeleteComment = async (commentId) => {
  try {
    await ElMessageBox.confirm('确定删除该条评论吗？', '提示', { type: 'warning' })
    await deleteComment(commentId)
    ElMessage.success('评论已删除')
    fetchDetail()
  } catch (err) {
    // cancelled
  }
}

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/community')
  }
}

onMounted(() => {
  fetchDetail()
})
</script>

<style scoped>
.post-detail-container {
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
.post-card {
  border-radius: 8px;
  padding: 24px;
}
.post-header {
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 20px;
  margin-bottom: 20px;
}
.post-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.post-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.4;
  margin: 0 0 16px;
}
.author-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.author-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.author-meta {
  display: flex;
  flex-direction: column;
}
.author-meta .name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.author-meta .date {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.rating-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rating-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.post-body {
  font-size: 16px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
  min-height: 180px;
}
.post-content :deep(p) {
  margin-bottom: 14px;
}
.comment-section {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.comment-header h3 {
  font-size: 18px;
  margin: 0 0 16px;
}
.comment-input-box {
  margin-bottom: 24px;
}
.comment-btn-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.comment-login-tip {
  padding: 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 6px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.comment-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.comment-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background-color: var(--el-fill-color-lighter);
  border-radius: 8px;
}
.comment-content-wrap {
  flex: 1;
}
.comment-user-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}
.comment-user {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.comment-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-right: auto;
}
.comment-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  margin: 0;
}
.no-comment {
  padding: 20px 0;
}
</style>
