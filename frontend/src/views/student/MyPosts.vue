<template>
  <div class="my-posts-container">
    <el-card shadow="never" class="box-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-title">我的面经与企业评价</span>
            <span class="card-sub">发布求职面经与企业评价，审核通过后将同步展示在公共社区</span>
          </div>
          <div class="header-actions">
            <el-button @click="router.push('/community')">浏览公共社区</el-button>
            <el-button type="primary" icon="Plus" @click="openCreateDialog">发布新面经/评价</el-button>
          </div>
        </div>
      </template>

      <el-table :data="posts" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="postType" label="类别" width="110">
          <template #default="{ row }">
            <el-tag :type="row.postType === 1 ? 'success' : 'warning'">
              {{ row.postTypeName }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="companyName" label="关联企业" width="160">
          <template #default="{ row }">
            <span>{{ row.companyName || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="auditStatus" label="审核状态" width="120">
          <template #default="{ row }">
            <el-tooltip v-if="row.auditStatus === 2" :content="row.auditRemark || '已被驳回'" placement="top">
              <el-tag type="danger" effect="plain" class="cursor-pointer">已驳回 (原因)</el-tag>
            </el-tooltip>
            <el-tag v-else-if="row.auditStatus === 1" type="success" effect="plain">审核通过</el-tag>
            <el-tag v-else type="warning" effect="plain">待审核</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="commentCount" label="评论数" width="90" align="center" />
        <el-table-column prop="createTime" label="发布时间" width="160" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row.id)">删除</el-button>
            <el-button v-if="row.auditStatus === 1" type="info" link size="small" @click="router.push(`/community/${row.id}`)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchPosts"
          @current-change="fetchPosts"
        />
      </div>
    </el-card>

    <!-- 发帖 / 编辑弹窗框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑我的帖子' : '发布求职面经 / 企业评价'"
      width="640px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
        <el-form-item label="类别" prop="postType">
          <el-radio-group v-model="form.postType">
            <el-radio :value="1">求职面经</el-radio>
            <el-radio :value="2">企业评价</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="如：字节跳动后端开发一面+二面详细复盘" maxlength="128" show-word-limit />
        </el-form-item>

        <el-form-item v-if="form.postType === 2" label="企业评分" prop="rating">
          <el-rate v-model="form.rating" :max="5" show-text :texts="['极不推荐', '待改进', '一般', '推荐', '极力推荐']" />
        </el-form-item>

        <el-form-item label="正文内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            placeholder="请详细记录面试轮次、技术问题、手撕算法、现场问答或企业文化感受..."
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            {{ isEdit ? '确认修改并重新审核' : '立即发布' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMyPosts, createPost, updatePost, deletePost } from '@/api/student'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const posts = ref([])

const pagination = reactive({
  current: 1,
  size: 10,
  total: 0
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const formRef = ref(null)
const form = reactive({
  postType: 1,
  title: '',
  rating: 5,
  content: '',
  companyId: null,
  positionId: null
})

const formRules = {
  postType: [{ required: true, message: '请选择类别', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入正文内容', trigger: 'blur' }]
}

const fetchPosts = async () => {
  loading.value = true
  try {
    const res = await getMyPosts({
      current: pagination.current,
      size: pagination.size
    })
    posts.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(form, {
    postType: 1,
    title: '',
    rating: 5,
    content: '',
    companyId: null,
    positionId: null
  })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    postType: row.postType,
    title: row.title,
    rating: row.rating || 5,
    content: row.content,
    companyId: row.companyId,
    positionId: row.positionId
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        postType: form.postType,
        title: form.title,
        content: form.content,
        rating: form.postType === 2 ? form.rating : null,
        companyId: form.companyId,
        positionId: form.positionId
      }
      if (isEdit.value) {
        await updatePost(editId.value, payload)
        ElMessage.success('修改成功，已重新提交审核')
      } else {
        await createPost(payload)
        ElMessage.success('发布成功，请等待管理员审核')
      }
      dialogVisible.value = false
      fetchPosts()
    } catch (err) {
      console.error(err)
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该帖子吗？删除后不可恢复。', '删除确认', { type: 'warning' })
    await deletePost(id)
    ElMessage.success('帖子删除成功')
    fetchPosts()
  } catch (err) {
    // cancelled
  }
}

onMounted(() => {
  fetchPosts()
})
</script>

<style scoped>
.my-posts-container {
  padding: 10px 0;
}
.box-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  margin-right: 12px;
}
.card-sub {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.header-actions {
  display: flex;
  gap: 10px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.cursor-pointer {
  cursor: pointer;
}
</style>
