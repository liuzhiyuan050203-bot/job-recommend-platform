<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">在线简历</span>
          <el-button type="primary" @click="openCreate">新建简历</el-button>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.isDefault === 1" type="success">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="updateTime" label="更新时间" width="180" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.isDefault !== 1" link @click="makeDefault(row)">设为默认</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="form.id ? '编辑简历' : '新建简历'" width="680px">
      <el-form label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="默认简历">
          <el-switch v-model="form.isDefault" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="教育经历">
          <el-input v-model="form.educationExp" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="项目经历">
          <el-input v-model="form.projectExp" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="实习经历">
          <el-input v-model="form.internshipExp" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="技能概述">
          <el-input v-model="form.skillDesc" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="自我评价">
          <el-input v-model="form.selfEvaluation" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="附件地址">
          <el-input v-model="form.attachmentUrl" maxlength="512" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createResume, deleteResume, getResumes, setDefaultResume, updateResume } from '@/api/student'

const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const rows = ref([])
const form = reactive({
  id: null,
  title: '',
  isDefault: 0,
  educationExp: '',
  projectExp: '',
  internshipExp: '',
  skillDesc: '',
  selfEvaluation: '',
  attachmentUrl: ''
})

function reset(data) {
  Object.assign(form, {
    id: null,
    title: '',
    isDefault: 0,
    educationExp: '',
    projectExp: '',
    internshipExp: '',
    skillDesc: '',
    selfEvaluation: '',
    attachmentUrl: ''
  }, data || {})
}

async function load() {
  loading.value = true
  try {
    rows.value = await getResumes()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  reset(null)
  visible.value = true
}

function openEdit(row) {
  reset(row)
  visible.value = true
}

async function submit() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写简历标题')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, id: undefined }
    if (form.id) await updateResume(form.id, payload)
    else await createResume(payload)
    ElMessage.success('已保存')
    visible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function makeDefault(row) {
  await setDefaultResume(row.id)
  ElMessage.success('已设为默认')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`删除简历「${row.title}」？`, '提示', { type: 'warning' })
  await deleteResume(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; }
</style>
