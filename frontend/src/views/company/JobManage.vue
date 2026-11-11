<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">职位管理</span>
            <span class="hint head-hint">新发布或修改后的职位需管理员审核，审核通过且上架后学生才能看到</span>
          </div>
          <el-button type="primary" icon="Plus" @click="openCreate">发布职位</el-button>
        </div>
      </template>
      <el-table v-loading="loading" :data="jobs" stripe>
        <el-table-column prop="title" label="职位名称" min-width="160" />
        <el-table-column prop="techDirection" label="技术方向" width="120" />
        <el-table-column label="地点" width="120">
          <template #default="{ row }">{{ row.province }} · {{ row.city }}</template>
        </el-table-column>
        <el-table-column label="薪资" width="150">
          <template #default="{ row }">{{ salaryText(row.salaryMin, row.salaryMax, row.salaryMonths) }}</template>
        </el-table-column>
        <el-table-column label="技能" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="name in row.tagNames || []" :key="name" size="small" class="tag">{{ name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核" width="110">
          <template #default="{ row }">
            <el-tooltip v-if="row.auditRemark" :content="row.auditRemark" placement="top">
              <el-tag :type="auditTagType(row.auditStatus)">{{ labelOf(AUDIT_STATUS, row.auditStatus) }}</el-tag>
            </el-tooltip>
            <el-tag v-else :type="auditTagType(row.auditStatus)">{{ labelOf(AUDIT_STATUS, row.auditStatus) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上架" width="120">
          <template #default="{ row }">
            <el-switch :model-value="row.shelfStatus === 1" @change="(val) => toggleShelf(row, val)" />
            <div v-if="row.shelfStatus === 1 && row.auditStatus !== 1" class="shelf-tip">
              {{ row.auditStatus === 2 ? '已驳回，修改后重新提交' : '审核通过后自动对学生可见' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="投递数" width="90">
          <template #default="{ row }">
            <el-button v-if="row.applyCount" link type="primary" @click="router.push({ path: '/company/candidates', query: { jobId: row.id } })">{{ row.applyCount }} 份</el-button>
            <span v-else class="muted">0</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" description="还没有发布职位">
            <el-button type="primary" @click="openCreate">发布第一个职位</el-button>
          </el-empty>
        </template>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page.current"
          v-model:page-size="page.size"
          :total="page.total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="visible" :title="form.id ? '编辑职位' : '发布职位'" width="760px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="职位名称" prop="title">
          <el-input v-model="form.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="职位分类" prop="categoryId">
          <el-cascader v-model="form.categoryId" :options="categories" :props="{ emitPath: false }" clearable style="width: 100%" />
        </el-form-item>
        <el-form-item label="技能标签" prop="tagIds">
          <div class="tag-field">
            <el-select v-model="form.tagIds" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="6"
              placeholder="至少选择 1 个，推荐与候选人匹配分都依据它" style="flex: 1">
              <el-option v-for="tag in skillTags" :key="tag.id" :label="`${tag.name}（${tag.direction}）`" :value="tag.id" />
            </el-select>
            <el-tooltip content="从职位名称、职责、任职要求里识别技能词表中的技能，追加到已选标签" placement="top">
              <el-button @click="extractTags">从描述提取</el-button>
            </el-tooltip>
          </div>
        </el-form-item>
        <el-form-item label="工作地点" required>
          <div class="place">
            <el-input v-model="form.province" placeholder="省份，如广东" />
            <el-input v-model="form.city" placeholder="城市，如深圳" />
            <el-input v-model="form.district" placeholder="区县" />
          </div>
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input v-model="form.address" maxlength="255" />
        </el-form-item>
        <el-form-item label="月薪(元)" required>
          <div class="place">
            <el-input-number v-model="form.salaryMin" :min="0" :step="1000" />
            <span>至</span>
            <el-input-number v-model="form.salaryMax" :min="0" :step="1000" />
            <el-input-number v-model="form.salaryMonths" :min="12" :max="24" />
            <span>薪</span>
          </div>
        </el-form-item>
        <el-form-item label="招聘人数" prop="headcount">
          <el-input-number v-model="form.headcount" :min="1" />
        </el-form-item>
        <el-form-item label="学历" prop="education">
          <el-select v-model="form.education" style="width: 180px">
            <el-option v-for="item in EDUCATION" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="经验" prop="experienceReq">
          <el-select v-model="form.experienceReq" style="width: 180px">
            <el-option v-for="item in EXPERIENCE" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="性质" prop="jobType">
          <el-select v-model="form.jobType" style="width: 180px">
            <el-option v-for="item in JOB_TYPE" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位职责">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="任职要求">
          <el-input v-model="form.requirement" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="福利">
          <el-input v-model="form.welfare" maxlength="500" />
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
import { useRoute, useRouter } from 'vue-router'
import { getCategories, getSkillTags } from '@/api/public'
import { createCompanyJob, deleteCompanyJob, getCompanyJob, getCompanyJobs, shelfCompanyJob, updateCompanyJob } from '@/api/company'
import { extractSkillIds } from '@/utils/jobText'
import { AUDIT_STATUS, EDUCATION, EXPERIENCE, JOB_TYPE, auditTagType, labelOf, mapCategoryOptions, salaryText } from '@/utils/job'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const jobs = ref([])
const categories = ref([])
const skillTags = ref([])
const formRef = ref()
const page = reactive({ current: 1, size: 10, total: 0 })

const emptyForm = () => ({
  id: null,
  title: '',
  categoryId: null,
  tagIds: [],
  province: '',
  city: '',
  district: '',
  address: '',
  salaryMin: 8000,
  salaryMax: 15000,
  salaryMonths: 12,
  headcount: 1,
  education: 2,
  experienceReq: 1,
  jobType: 3,
  description: '',
  requirement: '',
  welfare: ''
})
const form = reactive(emptyForm())
const rules = {
  title: [{ required: true, message: '请填写职位名称', trigger: 'blur' }],
  categoryId: [{ required: true, message: '请选择分类', trigger: 'change' }],
  headcount: [{ required: true, message: '请填写人数', trigger: 'change' }],
  education: [{ required: true, message: '请选择学历', trigger: 'change' }],
  experienceReq: [{ required: true, message: '请选择经验', trigger: 'change' }],
  jobType: [{ required: true, message: '请选择工作性质', trigger: 'change' }],
  tagIds: [{ type: 'array', required: true, min: 1, message: '请至少选择 1 个技能标签', trigger: 'change' }]
}

function extractTags() {
  const text = [form.title, form.description, form.requirement].filter(Boolean).join('\n')
  const found = extractSkillIds(text, skillTags.value)
  const added = found.filter((id) => !form.tagIds.includes(id))
  if (!found.length) {
    ElMessage.info('没有在职位名称、职责、任职要求里识别到技能词，请手动选择')
    return
  }
  if (form.tagIds.length + added.length > 20) {
    ElMessage.warning('技能标签最多 20 个，只追加了前面识别到的部分')
  }
  form.tagIds = [...form.tagIds, ...added].slice(0, 20)
  formRef.value?.validateField('tagIds')
  const names = added.map((id) => skillTags.value.find((t) => t.id === id)?.name).filter(Boolean)
  ElMessage.success(added.length ? `已追加：${names.join('、')}` : '识别到的技能都已在标签里')
}

function assignForm(data) {
  Object.assign(form, emptyForm(), data || {}, { tagIds: data?.tagIds ? [...data.tagIds] : [] })
}

async function load() {
  loading.value = true
  try {
    const res = await getCompanyJobs({ current: page.current, size: page.size })
    jobs.value = res.records || []
    page.total = res.total || 0
  } finally {
    loading.value = false
  }
}

function openCreate() {
  assignForm(null)
  visible.value = true
}

async function openEdit(row) {
  const detail = await getCompanyJob(row.id)
  assignForm(detail)
  visible.value = true
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    ElMessage.warning('请检查表单中标红的必填项')
    return
  }
  if (!form.province || !form.city) {
    ElMessage.warning('请填写省份和城市')
    return
  }
  if (form.salaryMin > form.salaryMax) {
    ElMessage.warning('最低月薪不能高于最高月薪')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, id: undefined }
    if (form.id) {
      await updateCompanyJob(form.id, payload)
    } else {
      await createCompanyJob(payload)
    }
    ElMessage.success(form.id ? '已保存，职位将重新进入审核' : '已发布，等待管理员审核后对学生可见')
    visible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleShelf(row, online) {
  try {
    await shelfCompanyJob(row.id, online ? 1 : 0)
    row.shelfStatus = online ? 1 : 0
    if (online) ElMessage.success(row.auditStatus === 1 ? '已上架，学生现在可以看到该职位' : '已设为上架，审核通过后自动对学生可见')
    else ElMessage.success('已下架，学生将看不到该职位')
  } catch {
    load()
  }
}

async function remove(row) {
  const ok = await ElMessageBox.confirm(
    `删除职位「${row.title}」后不可恢复，已收到的投递记录仍会保留。确定删除吗？`,
    '删除职位',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  ).then(() => true).catch(() => false)
  if (!ok) return
  await deleteCompanyJob(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  const [tree, tags] = await Promise.all([getCategories(), getSkillTags()])
  categories.value = mapCategoryOptions(tree)
  skillTags.value = tags || []
  load()
  if (route.query.create === '1') openCreate()
})
</script>

<style scoped>
.tag-field {
  display: flex;
  gap: 8px;
  width: 100%;
}
.head-hint { display: block; margin-top: 4px; }
.shelf-tip { font-size: 12px; color: #e6a23c; line-height: 1.4; margin-top: 2px; }
.muted { color: var(--el-text-color-secondary); }
.title { font-weight: 600; }
.tag { margin-right: 4px; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
.place { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
</style>
