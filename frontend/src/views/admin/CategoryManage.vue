<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">职位层级分类树管理</span>
            <span class="sub-title">叶子分类名称作为职位的技术方向(tech_direction)口径</span>
          </div>
          <el-button type="primary" icon="Plus" @click="openAddRootDialog">添加顶级分类</el-button>
        </div>
      </template>

      <!-- 树形表格 -->
      <el-table
        :data="categories"
        row-key="id"
        border
        default-expand-all
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="name" label="分类名称" min-width="200" />
        <el-table-column prop="id" label="分类 ID" width="100" align="center" />
        <el-table-column prop="sortNo" label="排序号" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="管理操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="success" link size="small" icon="Plus" @click="openAddChildDialog(row)">
              添加子类
            </el-button>
            <el-button type="primary" link size="small" icon="Edit" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" icon="Delete" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加 / 编辑分类弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item v-if="parentName" label="上级分类">
          <el-input :model-value="parentName" disabled />
        </el-form-item>

        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="如：后端开发 / 人工智能" />
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminCategories,
  addAdminCategory,
  updateAdminCategory,
  deleteAdminCategory
} from '@/api/admin'

const loading = ref(false)
const submitting = ref(false)
const categories = ref([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const parentName = ref('')

const formRef = ref(null)
const form = reactive({
  parentId: null,
  name: '',
  sortNo: 0,
  status: 1
})

const rules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
}

const dialogTitle = computed(() => {
  if (isEdit.value) return '编辑职位分类'
  if (form.parentId) return `在【${parentName.value}】下添加子分类`
  return '添加顶级职位分类'
})

const fetchCategories = async () => {
  loading.value = true
  try {
    const res = await getAdminCategories()
    categories.value = res || []
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const openAddRootDialog = () => {
  isEdit.value = false
  editId.value = null
  parentName.value = ''
  Object.assign(form, {
    parentId: null,
    name: '',
    sortNo: 0,
    status: 1
  })
  dialogVisible.value = true
}

const openAddChildDialog = (row) => {
  isEdit.value = false
  editId.value = null
  parentName.value = row.name
  Object.assign(form, {
    parentId: row.id,
    name: '',
    sortNo: 0,
    status: 1
  })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  parentName.value = ''
  Object.assign(form, {
    parentId: row.parentId,
    name: row.name,
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
        await updateAdminCategory(editId.value, form)
        ElMessage.success('分类更新成功')
      } else {
        await addAdminCategory(form)
        ElMessage.success('分类添加成功')
      }
      dialogVisible.value = false
      fetchCategories()
    } catch (err) {
      console.error(err)
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除分类【${row.name}】吗？若存在子分类或被职位引用将无法删除。`, '删除确认', {
      type: 'warning'
    })
    await deleteAdminCategory(row.id)
    ElMessage.success('分类删除成功')
    fetchCategories()
  } catch (err) {
    // cancelled or error handled by interceptor
  }
}

onMounted(() => {
  fetchCategories()
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
  margin-right: 12px;
}
.sub-title {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
