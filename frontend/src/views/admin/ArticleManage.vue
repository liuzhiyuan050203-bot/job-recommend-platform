<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">文章、双选会公告与政策发布</span>
          <div class="header-actions">
            <el-select v-model="filterType" placeholder="内容类别" clearable style="width: 130px" @change="handleSearch">
              <el-option label="双选会公告" :value="1" />
              <el-option label="就业政策" :value="2" />
              <el-option label="新闻资讯" :value="3" />
            </el-select>

            <el-select v-model="filterStatus" placeholder="发布状态" clearable style="width: 120px" @change="handleSearch">
              <el-option label="已发布" :value="1" />
              <el-option label="草稿" :value="0" />
              <el-option label="已下线" :value="2" />
            </el-select>

            <el-input
              v-model="keyword"
              placeholder="搜索标题或摘要"
              clearable
              style="width: 220px"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #append>
                <el-button icon="Search" @click="handleSearch" />
              </template>
            </el-input>

            <el-button type="primary" icon="Plus" @click="openAddDialog">撰写新文章</el-button>
          </div>
        </div>
      </template>

      <el-table :data="articles" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="articleType" label="类别" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.articleType)">{{ row.articleTypeName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.topFlag === 1" type="danger" size="small" style="margin-right: 4px">顶</el-tag>
            <span>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="publisherName" label="发布人" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : (row.status === 2 ? 'info' : 'warning')">
              {{ row.status === 1 ? '已发布' : (row.status === 2 ? '已下线' : '草稿') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="viewCount" label="阅读量" width="90" align="center" />
        <el-table-column prop="publishTime" label="发布时间" width="160">
          <template #default="{ row }">{{ row.publishTime || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 1"
              type="success"
              link
              size="small"
              @click="handleToggleStatus(row, 1)"
            >
              发布
            </el-button>
            <el-button
              v-else
              type="info"
              link
              size="small"
              @click="handleToggleStatus(row, 2)"
            >
              撤回下线
            </el-button>

            <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row.id)">删除</el-button>
            <el-button v-if="row.status === 1" type="primary" link size="small" @click="viewDetail(row.id)">预览</el-button>
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
          @size-change="fetchArticles"
          @current-change="fetchArticles"
        />
      </div>
    </el-card>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑文章内容' : '撰写新公告 / 政策'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类别" prop="articleType">
              <el-select v-model="form.articleType" placeholder="选择类别" style="width: 100%">
                <el-option label="双选会公告" :value="1" />
                <el-option label="就业政策" :value="2" />
                <el-option label="新闻资讯" :value="3" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="置顶显示">
              <el-switch v-model="form.topFlag" :active-value="1" :inactive-value="0" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="直接发布">
              <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="文章标题" prop="title">
          <el-input v-model="form.title" placeholder="如：2026年高校毕业生春季促就业双选会通知" maxlength="128" show-word-limit />
        </el-form-item>

        <el-form-item label="封面 URL">
          <el-input v-model="form.coverUrl" placeholder="文章封面图网络地址（选填）" />
        </el-form-item>

        <el-form-item label="概要摘要">
          <el-input
            v-model="form.summary"
            type="textarea"
            :rows="2"
            placeholder="简要概括文章主要内容（供列表展示）..."
            maxlength="300"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="文章正文" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="正文详情内容（支持换行分段）..."
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            {{ form.status === 1 ? '立即发布' : '保存草稿' }}
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
import {
  getAdminArticles,
  addAdminArticle,
  updateAdminArticle,
  updateAdminArticleStatus,
  deleteAdminArticle
} from '@/api/admin'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const articles = ref([])
const filterType = ref(null)
const filterStatus = ref(null)
const keyword = ref('')

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
  articleType: 1,
  title: '',
  coverUrl: '',
  summary: '',
  content: '',
  topFlag: 0,
  status: 1
})

const rules = {
  articleType: [{ required: true, message: '请选择类别', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入正文内容', trigger: 'blur' }]
}

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
      type: filterType.value || undefined,
      status: filterStatus.value !== null ? filterStatus.value : undefined,
      keyword: keyword.value.trim() || undefined
    }
    const res = await getAdminArticles(params)
    articles.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchArticles()
}

const openAddDialog = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(form, {
    articleType: 1,
    title: '',
    coverUrl: '',
    summary: '',
    content: '',
    topFlag: 0,
    status: 1
  })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    articleType: row.articleType,
    title: row.title,
    coverUrl: row.coverUrl || '',
    summary: row.summary || '',
    content: row.content,
    topFlag: row.topFlag,
    status: row.status
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (isEdit.value) {
        await updateAdminArticle(editId.value, form)
        ElMessage.success('文章更新成功')
      } else {
        await addAdminArticle(form)
        ElMessage.success('文章发布/保存成功')
      }
      dialogVisible.value = false
      fetchArticles()
    } catch (err) {
      console.error(err)
    } finally {
      submitting.value = false
    }
  })
}

const handleToggleStatus = async (row, targetStatus) => {
  const actionText = targetStatus === 1 ? '发布上线' : '撤回下线'
  try {
    await updateAdminArticleStatus(row.id, targetStatus)
    ElMessage.success(`文章已${actionText}`)
    fetchArticles()
  } catch (err) {
    console.error(err)
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该文章吗？', '删除确认', { type: 'warning' })
    await deleteAdminArticle(id)
    ElMessage.success('文章删除成功')
    fetchArticles()
  } catch (err) {
    // cancelled
  }
}

const viewDetail = (id) => {
  router.push(`/articles/${id}`)
}

onMounted(() => {
  fetchArticles()
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
  flex-wrap: wrap;
  gap: 12px;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
