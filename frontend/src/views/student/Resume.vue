<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">在线简历</span>
            <span class="hint head-hint">投递时选择其中一份发给企业；默认简历会被优先选中。上传 PDF 识别的技能会自动同步到默认简历的「技能概述」</span>
          </div>
          <el-button type="primary" icon="Plus" @click="openCreate">新建简历</el-button>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="内容完整度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="filled(row)" :stroke-width="8" :status="filled(row) === 100 ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.isDefault === 1" type="success">默认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ String(row.updateTime || '').replace('T', ' ').slice(0, 16) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="row.isDefault !== 1" link @click="makeDefault(row)">设为默认</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" description="还没有在线简历，投递职位前需要先创建一份">
            <el-button type="primary" @click="openCreate">新建简历</el-button>
          </el-empty>
        </template>
      </el-table>
    </el-card>

    <el-dialog v-model="visible" :title="form.id ? '编辑简历' : '新建简历'" width="680px">
      <el-form label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="128" placeholder="如：张三-后端开发-校招简历" />
        </el-form-item>
        <el-form-item label="默认简历">
          <el-switch v-model="form.isDefault" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="教育经历">
          <el-input v-model="form.educationExp" type="textarea" :rows="3" placeholder="学校、专业、学历、毕业时间、主修课程或成绩排名" />
        </el-form-item>
        <el-form-item label="项目经历">
          <el-input v-model="form.projectExp" type="textarea" :rows="3" placeholder="项目名称、你的角色、使用的技术与取得的成果" />
        </el-form-item>
        <el-form-item label="实习经历">
          <el-input v-model="form.internshipExp" type="textarea" :rows="3" placeholder="公司、岗位、时间与主要工作；没有可填「暂无」" />
        </el-form-item>
        <el-form-item label="技能概述">
          <el-input v-model="form.skillDesc" type="textarea" :rows="3" placeholder="如：Java、Spring Boot、MySQL、Redis（企业会据此和职位技能做匹配）" />
        </el-form-item>
        <el-form-item label="自我评价">
          <el-input v-model="form.selfEvaluation" type="textarea" :rows="3" placeholder="求职意向、优势与期望" />
        </el-form-item>
        <el-form-item label="附件地址">
          <el-input v-model="form.attachmentUrl" maxlength="512" placeholder="选填：附件简历的在线链接（http/https）" />
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

const SECTIONS = ['educationExp', 'projectExp', 'internshipExp', 'skillDesc', 'selfEvaluation']
function filled(row) {
  return Math.round((SECTIONS.filter((k) => String(row[k] || '').trim()).length / SECTIONS.length) * 100)
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
  const ok = await ElMessageBox.confirm(`删除简历「${row.title}」？删除后无法恢复。`, '删除简历', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deleteResume(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.head-hint { display: block; margin-top: 4px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; }
</style>
