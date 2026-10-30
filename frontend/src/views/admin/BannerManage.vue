<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">首页轮播图配置管理</span>
          <el-button type="primary" icon="Plus" @click="openAddDialog">添加轮播图</el-button>
        </div>
      </template>

      <el-table :data="banners" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="轮播图标题" min-width="160" />
        <el-table-column label="预览图" width="160">
          <template #default="{ row }">
            <el-image
              :src="row.imageUrl"
              fit="cover"
              class="banner-thumb"
              :preview-src-list="[row.imageUrl]"
            />
          </template>
        </el-table-column>
        <el-table-column prop="linkUrl" label="跳转链接" min-width="180">
          <template #default="{ row }">
            <span class="link-text">{{ row.linkUrl || '无跳转' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="sortNo" label="排序号" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="投放周期" width="200">
          <template #default="{ row }">
            <div class="time-range-text">
              <div>起：{{ row.startTime ? row.startTime.substring(0, 16) : '不限' }}</div>
              <div>止：{{ row.endTime ? row.endTime.substring(0, 16) : '不限' }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[5, 10, 20]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchBanners"
          @current-change="fetchBanners"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑轮播图' : '新增首页轮播图'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="轮播图标题" prop="title">
          <el-input v-model="form.title" placeholder="如：2026 届秋季校园大型双选会" />
        </el-form-item>

        <el-form-item label="图片 URL" prop="imageUrl">
          <el-input v-model="form.imageUrl" placeholder="输入图片网络访问链接" />
        </el-form-item>

        <div v-if="form.imageUrl" class="img-preview-box">
          <el-image :src="form.imageUrl" fit="cover" style="width: 100%; height: 140px; border-radius: 6px;" />
        </div>

        <el-form-item label="跳转链接">
          <el-input v-model="form.linkUrl" placeholder="如：/articles/1 或外部链接" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="排序号" prop="sortNo">
              <el-input-number v-model="form.sortNo" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio :value="1">启用</el-radio>
                <el-radio :value="0">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始时间">
              <el-date-picker
                v-model="form.startTime"
                type="datetime"
                placeholder="投放开始时间"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间">
              <el-date-picker
                v-model="form.endTime"
                type="datetime"
                placeholder="投放结束时间"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
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
import { getAdminBanners, addAdminBanner, updateAdminBanner, deleteAdminBanner } from '@/api/admin'

const loading = ref(false)
const submitting = ref(false)
const banners = ref([])

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
  title: '',
  imageUrl: '',
  linkUrl: '',
  sortNo: 0,
  status: 1,
  startTime: null,
  endTime: null
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  imageUrl: [{ required: true, message: '请输入图片 URL', trigger: 'blur' }]
}

const fetchBanners = async () => {
  loading.value = true
  try {
    const res = await getAdminBanners({
      current: pagination.current,
      size: pagination.size
    })
    banners.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const openAddDialog = () => {
  isEdit.value = false
  editId.value = null
  Object.assign(form, {
    title: '',
    imageUrl: 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=1200&auto=format&fit=crop',
    linkUrl: '',
    sortNo: 0,
    status: 1,
    startTime: null,
    endTime: null
  })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    title: row.title,
    imageUrl: row.imageUrl,
    linkUrl: row.linkUrl || '',
    sortNo: row.sortNo,
    status: row.status,
    startTime: row.startTime || null,
    endTime: row.endTime || null
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
        await updateAdminBanner(editId.value, form)
        ElMessage.success('轮播图更新成功')
      } else {
        await addAdminBanner(form)
        ElMessage.success('轮播图添加成功')
      }
      dialogVisible.value = false
      fetchBanners()
    } catch (err) {
      console.error(err)
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该轮播图吗？', '删除确认', { type: 'warning' })
    await deleteAdminBanner(id)
    ElMessage.success('轮播图删除成功')
    fetchBanners()
  } catch (err) {
    // cancelled
  }
}

onMounted(() => {
  fetchBanners()
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
.banner-thumb {
  width: 120px;
  height: 60px;
  border-radius: 4px;
}
.link-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}
.time-range-text {
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.img-preview-box {
  margin: 0 0 16px 100px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
