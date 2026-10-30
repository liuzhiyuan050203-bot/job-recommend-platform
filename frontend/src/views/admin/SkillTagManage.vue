<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">技能标签字典体系管理</span>
          <div class="header-actions">
            <el-select v-model="filterDirection" placeholder="按技术方向筛选" clearable style="width: 150px" @change="handleSearch">
              <el-option label="后端开发" value="后端开发" />
              <el-option label="前端开发" value="前端开发" />
              <el-option label="数据开发" value="数据开发" />
              <el-option label="人工智能" value="人工智能" />
              <el-option label="通用技术" value="通用技术" />
            </el-select>

            <el-input
              v-model="keyword"
              placeholder="搜索技能名称"
              clearable
              style="width: 220px"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #append>
                <el-button icon="Search" @click="handleSearch" />
              </template>
            </el-input>

            <el-button type="primary" icon="Plus" @click="openAddDialog">添加技能标签</el-button>
          </div>
        </div>
      </template>

      <el-table :data="tags" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="技能名称" min-width="160">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="direction" label="所属技术方向" min-width="150" />
        <el-table-column prop="sortNo" label="排序号" width="100" align="center" />
        <el-table-column prop="status" label="启用状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" width="160" />
        <el-table-column label="管理操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
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
          @size-change="fetchTags"
          @current-change="fetchTags"
        />
      </div>
    </el-card>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑技能标签' : '添加新技能标签'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="技能名称" prop="name">
          <el-input v-model="form.name" placeholder="如：Spring Cloud / Kubernetes" />
        </el-form-item>

        <el-form-item label="技术方向" prop="direction">
          <el-select v-model="form.direction" placeholder="选择或输入技术方向" filterable allow-create style="width: 100%">
            <el-option label="后端开发" value="后端开发" />
            <el-option label="前端开发" value="前端开发" />
            <el-option label="数据开发" value="数据开发" />
            <el-option label="人工智能" value="人工智能" />
            <el-option label="算法工程" value="算法工程" />
            <el-option label="通用技术" value="通用技术" />
          </el-select>
        </el-form-item>

        <el-form-item label="排序号" prop="sortNo">
          <el-input-number v-model="form.sortNo" :min="0" :max="999" style="width: 100%" />
        </el-form-item>

        <el-form-item label="启用状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminSkillTags,
  addAdminSkillTag,
  updateAdminSkillTag,
  deleteAdminSkillTag
} from '@/api/admin'

const loading = ref(false)
const submitting = ref(false)
const tags = ref([])
const filterDirection = ref('')
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
  name: '',
  direction: '后端开发',
  sortNo: 0,
  status: 1
})

const rules = {
  name: [{ required: true, message: '请输入技能名称', trigger: 'blur' }],
  direction: [{ required: true, message: '请指定技术方向', trigger: 'change' }]
}

const fetchTags = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      direction: filterDirection.value || undefined,
      keyword: keyword.value.trim() || undefined
    }
    const res = await getAdminSkillTags(params)
    tags.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchTags()
}

const openAddDialog = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(form, {
    name: '',
    direction: filterDirection.value || '后端开发',
    sortNo: 0,
    status: 1
  })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    direction: row.direction,
    sortNo: row.sortNo,
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
        await updateAdminSkillTag(editId.value, form)
        ElMessage.success('技能标签更新成功')
      } else {
        await addAdminSkillTag(form)
        ElMessage.success('技能标签添加成功')
      }
      dialogVisible.value = false
      fetchTags()
    } catch (err) {
      console.error(err)
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除技能标签【${row.name}】吗？`, '删除确认', { type: 'warning' })
    await deleteAdminSkillTag(row.id)
    ElMessage.success('技能标签删除成功')
    fetchTags()
  } catch (err) {
    // cancelled
  }
}

onMounted(() => {
  fetchTags()
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
