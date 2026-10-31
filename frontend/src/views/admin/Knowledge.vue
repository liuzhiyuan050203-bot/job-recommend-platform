<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col v-for="item in cards" :key="item.label" :xs="12" :sm="8" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ item.label }}</div>
          <div class="stat-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">知识库管理</span>
          <div class="actions">
            <el-button type="primary" @click="uploadVisible = true">上传文档</el-button>
            <el-button
              v-for="item in sources"
              :key="item.value"
              :loading="rebuilding === item.value"
              @click="rebuild(item)"
            >重建{{ item.label }}</el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" class="filters" @submit.prevent>
        <el-form-item label="类型">
          <el-select v-model="query.docType" clearable placeholder="全部" style="width: 150px">
            <el-option v-for="(label, value) in DOC_TYPES" :key="value" :label="label" :value="Number(value)" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="query.sourceType" clearable placeholder="全部" style="width: 150px">
            <el-option v-for="(label, value) in SOURCE_TYPES" :key="value" :label="label" :value="Number(value)" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="query.q" clearable placeholder="标题或文档键" style="width: 200px" @keyup.enter="searchList" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchList">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="records" size="small" empty-text="暂无文档">
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ DOC_TYPES[row.docType] || row.docType }}</template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">{{ SOURCE_TYPES[row.sourceType] || row.sourceType }}</template>
        </el-table-column>
        <el-table-column prop="chunkCount" label="切片" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ statusOf(row) }}</template>
        </el-table-column>
        <el-table-column prop="updateTime" label="更新时间" width="170" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="rowKey === row.docKey" @click="reindexOne(row)">重建</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :current-page="query.current"
          :page-size="query.size"
          :total="total"
          @current-change="changePage"
        />
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <span class="title">检索测试</span>
      </template>
      <div class="search-row">
        <el-input v-model="searchQ" placeholder="输入问题，查看命中的切片" @keyup.enter="runSearch" />
        <el-button type="primary" :loading="searching" @click="runSearch">检索</el-button>
      </div>
      <div v-if="hits.length" class="hits">
        <div v-for="(hit, index) in hits" :key="index" class="hit">
          <div class="hit-title">
            {{ hit.title || '资料' }}
            <span v-if="hit.section"> / {{ hit.section }}</span>
            <span class="score">相关度 {{ hit.score }}</span>
          </div>
          <div class="hit-content">{{ hit.content }}</div>
        </div>
      </div>
      <el-empty v-else-if="searched" description="没有超过阈值的切片" />
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传文档" width="480px" @closed="resetUpload">
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="uploadForm.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="uploadForm.docType" style="width: 100%">
            <el-option v-for="(label, value) in DOC_TYPES" :key="value" :label="label" :value="Number(value)" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <input type="file" accept=".md,.txt,text/markdown,text/plain" @change="onFile" />
          <div class="file-hint">仅支持 .md / .txt，不超过 512KB</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传并索引</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteKnowledge,
  knowledgeDocuments,
  knowledgeStats,
  reindexKnowledge,
  searchKnowledge,
  uploadKnowledge
} from '@/api/ai'

const DOC_TYPES = {
  1: '就业政策',
  2: '平台使用指南',
  3: '面经精选',
  4: '企业招聘须知',
  5: '求职指导',
  6: '手续FAQ',
  7: '职位信息'
}
const SOURCE_TYPES = {
  1: '手工录入',
  2: '公告同步',
  3: '政策同步',
  4: '知识库文件',
  5: '职位同步',
  6: '管理员上传'
}
const sources = [
  { value: 'knowledge', label: '知识库文件' },
  { value: 'cms', label: '公告政策' },
  { value: 'jobs', label: '职位' },
  { value: 'uploads', label: '上传' },
  { value: 'all', label: '全部' }
]

const stats = ref({})
const records = ref([])
const total = ref(0)
const loading = ref(false)
const rebuilding = ref('')
const rowKey = ref('')
const query = reactive({ current: 1, size: 10, docType: undefined, sourceType: undefined, q: '' })
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadForm = reactive({ title: '', docType: 1, file: null })
const searchQ = ref('')
const searching = ref(false)
const searched = ref(false)
const hits = ref([])

const cards = computed(() => {
  const data = stats.value || {}
  return [
    { label: '文档数', value: data.documents ?? '-' },
    { label: '切片数', value: data.chunks ?? '-' },
    { label: '向量条数', value: data.chromaCount ?? '-' },
    { label: '相关度阈值', value: data.scoreThreshold ?? '-' }
  ]
})

function statusOf(row) {
  const chunks = Number(row.chunkCount || 0)
  const failed = Number(row.failed || 0)
  const embedded = Number(row.embedded || 0)
  if (failed > 0) {
    return '失败'
  }
  if (chunks > 0 && embedded >= chunks) {
    return '已入库'
  }
  return '待处理'
}

async function loadStats() {
  stats.value = await knowledgeStats()
}

async function loadDocs() {
  loading.value = true
  try {
    const data = await knowledgeDocuments({
      current: query.current,
      size: query.size,
      docType: query.docType || undefined,
      sourceType: query.sourceType || undefined,
      q: query.q || undefined
    })
    records.value = data?.records || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function searchList() {
  query.current = 1
  loadDocs()
}

function changePage(page) {
  query.current = page
  loadDocs()
}

function onFile(event) {
  const file = event.target.files && event.target.files[0]
  uploadForm.file = file || null
}

function resetUpload() {
  uploadForm.title = ''
  uploadForm.docType = 1
  uploadForm.file = null
}

async function submitUpload() {
  if (!uploadForm.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  if (!uploadForm.file) {
    ElMessage.warning('请选择文件')
    return
  }
  const name = uploadForm.file.name.toLowerCase()
  if (!name.endsWith('.md') && !name.endsWith('.txt')) {
    ElMessage.warning('只支持 .md 或 .txt 文件')
    return
  }
  if (uploadForm.file.size > 512 * 1024) {
    ElMessage.warning('文件不能超过 512KB')
    return
  }
  const form = new FormData()
  form.append('file', uploadForm.file)
  form.append('title', uploadForm.title.trim())
  form.append('docType', String(uploadForm.docType))
  uploading.value = true
  try {
    await uploadKnowledge(form)
    ElMessage.success('上传并索引完成')
    uploadVisible.value = false
    await Promise.all([loadStats(), loadDocs()])
  } finally {
    uploading.value = false
  }
}

async function reindexOne(row) {
  rowKey.value = row.docKey
  try {
    await reindexKnowledge({ docKey: row.docKey })
    ElMessage.success('已重新索引')
    await Promise.all([loadStats(), loadDocs()])
  } finally {
    rowKey.value = ''
  }
}

async function rebuild(item) {
  const extra = item.value === 'jobs' || item.value === 'all' ? '职位重建大约需要 50 秒。' : ''
  try {
    await ElMessageBox.confirm(`确认重建「${item.label}」？${extra}`, '重建索引', { type: 'warning' })
  } catch {
    return
  }
  rebuilding.value = item.value
  try {
    await reindexKnowledge({ source: item.value })
    ElMessage.success('重新索引完成')
    await Promise.all([loadStats(), loadDocs()])
  } finally {
    rebuilding.value = ''
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`删除文档「${row.title}」及其切片？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  await deleteKnowledge(row.docKey)
  ElMessage.success('已删除')
  await Promise.all([loadStats(), loadDocs()])
}

async function runSearch() {
  if (!searchQ.value.trim()) {
    ElMessage.warning('请输入检索问题')
    return
  }
  searching.value = true
  searched.value = true
  try {
    const data = await searchKnowledge({ q: searchQ.value.trim(), topK: 4 })
    hits.value = data?.results || []
  } finally {
    searching.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadStats(), loadDocs()])
})
</script>

<style scoped>
.page-container { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.title { font-weight: 600; font-size: 16px; }
.stat-label { color: #909399; font-size: 13px; }
.stat-value { margin-top: 6px; font-size: 18px; font-weight: 600; }
.filters { margin-bottom: 8px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.search-row { display: flex; gap: 8px; }
.hits { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.hit { background: #f6f8fa; border-radius: 8px; padding: 10px 12px; }
.hit-title { font-size: 14px; }
.score { color: #909399; margin-left: 8px; font-size: 12px; }
.hit-content { margin-top: 6px; color: #606266; white-space: pre-wrap; line-height: 1.6; }
.file-hint { color: #909399; font-size: 12px; margin-top: 4px; }
</style>
