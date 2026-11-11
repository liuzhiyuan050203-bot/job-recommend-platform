<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">社区内容审核（面经、企业评价与跟评）</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 标签页 1：帖子审核 (面经与评价) -->
        <el-tab-pane label="面经与企业评价" name="posts">
          <div class="filter-bar">
            <el-select v-model="postFilterStatus" placeholder="审核状态" clearable style="width: 130px" @change="fetchPosts">
              <el-option label="待审核" :value="0" />
              <el-option label="已通过" :value="1" />
              <el-option label="已驳回" :value="2" />
            </el-select>

            <el-input
              v-model="postKeyword"
              placeholder="搜索面经标题或内容"
              clearable
              style="width: 250px"
              @keyup.enter="fetchPosts"
              @clear="fetchPosts"
            >
              <template #append>
                <el-button icon="Search" @click="fetchPosts" />
              </template>
            </el-input>
          </div>

          <el-table :data="posts" stripe style="width: 100%" v-loading="postLoading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="postType" label="类别" width="110">
              <template #default="{ row }">
                <el-tag :type="row.postType === 1 ? 'success' : 'warning'">
                  {{ row.postTypeName }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="authorName" label="发布人" width="120" />
            <el-table-column prop="companyName" label="关联企业" width="140">
              <template #default="{ row }">{{ row.companyName || '-' }}</template>
            </el-table-column>
            <el-table-column prop="rating" label="评分" width="90">
              <template #default="{ row }">
                <span v-if="row.rating">{{ row.rating }} 星</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="auditStatus" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.auditStatus === 1 ? 'success' : (row.auditStatus === 2 ? 'danger' : 'warning')">
                  {{ row.auditStatus === 1 ? '已通过' : (row.auditStatus === 2 ? '已驳回' : '待审') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createTime" label="发布时间" width="160" />
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="success" link size="small" @click="openPostAuditDialog(row, 1)">通过</el-button>
                <el-button type="warning" link size="small" @click="openPostAuditDialog(row, 2)">驳回</el-button>
                <el-button type="danger" link size="small" @click="handleDeletePost(row.id)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty v-if="!postLoading" description="没有符合条件的帖子" />
            </template>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="postPagination.current"
              v-model:page-size="postPagination.size"
              :total="postPagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchPosts"
              @current-change="fetchPosts"
            />
          </div>
        </el-tab-pane>

        <!-- 标签页 2：评论审核 -->
        <el-tab-pane label="社区跟评审核" name="comments">
          <div class="filter-bar">
            <el-select v-model="commentFilterStatus" placeholder="审核状态" clearable style="width: 130px" @change="fetchComments">
              <el-option label="待审核" :value="0" />
              <el-option label="已通过" :value="1" />
              <el-option label="已驳回" :value="2" />
            </el-select>

            <el-input
              v-model="commentKeyword"
              placeholder="搜索评论内容"
              clearable
              style="width: 250px"
              @keyup.enter="fetchComments"
              @clear="fetchComments"
            >
              <template #append>
                <el-button icon="Search" @click="fetchComments" />
              </template>
            </el-input>
          </div>

          <el-table :data="comments" stripe style="width: 100%" v-loading="commentLoading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="postTitle" label="所属帖子" min-width="160" show-overflow-tooltip />
            <el-table-column prop="authorName" label="评论人" width="120" />
            <el-table-column prop="content" label="评论内容" min-width="220" show-overflow-tooltip />
            <el-table-column prop="auditStatus" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.auditStatus === 1 ? 'success' : (row.auditStatus === 2 ? 'danger' : 'warning')">
                  {{ row.auditStatus === 1 ? '已通过' : (row.auditStatus === 2 ? '已驳回' : '待审') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createTime" label="发表时间" width="160" />
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="success" link size="small" @click="openCommentAuditDialog(row, 1)">通过</el-button>
                <el-button type="warning" link size="small" @click="openCommentAuditDialog(row, 2)">驳回</el-button>
                <el-button type="danger" link size="small" @click="handleDeleteComment(row.id)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty v-if="!commentLoading" description="没有符合条件的评论" />
            </template>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="commentPagination.current"
              v-model:page-size="commentPagination.size"
              :total="commentPagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchComments"
              @current-change="fetchComments"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 审核弹窗 -->
    <el-dialog v-model="auditDialogVisible" :title="auditStatus === 1 ? '审核通过确认' : '审核驳回'" width="450px">
      <el-form label-width="80px">
        <el-form-item label="操作结论">
          <el-tag :type="auditStatus === 1 ? 'success' : 'danger'" size="large">
            {{ auditStatus === 1 ? '审核通过 (公开展示)' : '审核驳回' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="审核说明">
          <el-input v-model="auditRemark" type="textarea" :rows="3" placeholder="请输入审核意见或合规提醒..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="auditDialogVisible = false">取消</el-button>
          <el-button :type="auditStatus === 1 ? 'success' : 'danger'" :loading="submittingAudit" @click="handleConfirmAudit">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminPosts,
  auditAdminPost,
  deleteAdminPost,
  getAdminComments,
  auditAdminComment,
  deleteAdminComment
} from '@/api/admin'

const activeTab = ref('posts')
const route = useRoute()

// 帖子列表状态
const postLoading = ref(false)
const posts = ref([])
const postFilterStatus = ref(0)
const postKeyword = ref('')
const postPagination = reactive({ current: 1, size: 10, total: 0 })

// 评论列表状态
const commentLoading = ref(false)
const comments = ref([])
const commentFilterStatus = ref(0)
const commentKeyword = ref('')
const commentPagination = reactive({ current: 1, size: 10, total: 0 })

// 审核弹窗通用
const auditDialogVisible = ref(false)
const auditType = ref('post') // 'post' or 'comment'
const auditTargetId = ref(null)
const auditStatus = ref(1)
const auditRemark = ref('')
const submittingAudit = ref(false)

const fetchPosts = async () => {
  postLoading.value = true
  try {
    const params = {
      current: postPagination.current,
      size: postPagination.size,
      auditStatus: postFilterStatus.value !== null ? postFilterStatus.value : undefined,
      keyword: postKeyword.value.trim() || undefined
    }
    const res = await getAdminPosts(params)
    posts.value = res.records || []
    postPagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    postLoading.value = false
  }
}

const fetchComments = async () => {
  commentLoading.value = true
  try {
    const params = {
      current: commentPagination.current,
      size: commentPagination.size,
      auditStatus: commentFilterStatus.value !== null ? commentFilterStatus.value : undefined,
      keyword: commentKeyword.value.trim() || undefined
    }
    const res = await getAdminComments(params)
    comments.value = res.records || []
    commentPagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    commentLoading.value = false
  }
}

const handleTabChange = (tabName) => {
  if (tabName === 'posts') {
    fetchPosts()
  } else {
    fetchComments()
  }
}

const openPostAuditDialog = (row, status) => {
  auditType.value = 'post'
  auditTargetId.value = row.id
  auditStatus.value = status
  auditRemark.value = status === 1 ? '内容积极客观，真实有效，符合社区规范。' : '包含敏感信息或不文明表达，予以驳回。'
  auditDialogVisible.value = true
}

const openCommentAuditDialog = (row, status) => {
  auditType.value = 'comment'
  auditTargetId.value = row.id
  auditStatus.value = status
  auditRemark.value = status === 1 ? '审核通过' : '评论内容违规，予以驳回。'
  auditDialogVisible.value = true
}

const handleConfirmAudit = async () => {
  submittingAudit.value = true
  try {
    const payload = {
      auditStatus: auditStatus.value,
      auditRemark: auditRemark.value.trim()
    }
    if (auditType.value === 'post') {
      await auditAdminPost(auditTargetId.value, payload)
      ElMessage.success('帖子审核操作成功')
      fetchPosts()
    } else {
      await auditAdminComment(auditTargetId.value, payload)
      ElMessage.success('评论审核操作成功')
      fetchComments()
    }
    auditDialogVisible.value = false
  } catch (err) {
    console.error(err)
  } finally {
    submittingAudit.value = false
  }
}

const handleDeletePost = async (id) => {
  try {
    await ElMessageBox.confirm('确定下架并删除该违规帖子吗？', '删除确认', { type: 'warning' })
    await deleteAdminPost(id)
    ElMessage.success('帖子删除成功')
    fetchPosts()
  } catch (err) {
    // cancelled
  }
}

const handleDeleteComment = async (id) => {
  try {
    await ElMessageBox.confirm('确定下架并删除该违规评论吗？', '删除确认', { type: 'warning' })
    await deleteAdminComment(id)
    ElMessage.success('评论删除成功')
    fetchComments()
  } catch (err) {
    // cancelled
  }
}

onMounted(() => {
  if (route.query.tab === 'comments') {
    activeTab.value = 'comments'
    fetchComments()
    return
  }
  fetchPosts()
})
</script>

<style scoped>
.page-container {
  padding: 10px 0;
}
.table-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
