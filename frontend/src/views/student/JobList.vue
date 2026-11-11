<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">职位搜索</span>
          <span class="hint">共 {{ page.total }} 个在招职位 · 标「估算薪资」的职位官网未公布薪资</span>
        </div>
      </template>
      <el-form class="filters" label-width="72px" @submit.prevent="search">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12" :lg="8">
            <el-form-item label="关键词">
              <el-input v-model="query.keyword" clearable placeholder="职位名称或企业名称" @keyup.enter="search" @clear="search" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="技术方向">
              <el-select v-model="query.techDirection" clearable filterable placeholder="全部" @change="search">
                <el-option v-for="item in directions" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="城市">
              <el-select v-model="query.city" clearable filterable allow-create default-first-option placeholder="全部" @change="search">
                <el-option v-for="item in CITIES" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="学历">
              <el-select v-model="query.education" clearable placeholder="不限" @change="search">
                <el-option v-for="item in EDUCATION.filter((e) => e.value > 0)" :key="item.value" :label="`${item.label}及以下要求`" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="工作性质">
              <el-select v-model="query.jobType" clearable placeholder="不限" @change="search">
                <el-option v-for="item in JOB_TYPE" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="8">
            <el-form-item label="月薪">
              <div class="salary-range">
                <el-input-number v-model="query.salaryMin" :min="0" :step="1000" :controls="false" placeholder="最低（元）" />
                <span class="dash">至</span>
                <el-input-number v-model="query.salaryMax" :min="0" :step="1000" :controls="false" placeholder="最高（元）" />
              </div>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="来源">
              <el-select v-model="query.source" placeholder="全部来源" @change="search">
                <el-option v-for="item in JOB_SOURCE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="12" :sm="6" :lg="4">
            <el-form-item label="排序">
              <el-select v-model="query.sort" @change="search">
                <el-option label="最新发布" value="newest" />
                <el-option label="薪资最高" value="salary" />
                <el-option label="浏览最多" value="hot" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="8">
            <el-form-item label-width="0" class="filter-actions">
              <el-button type="primary" icon="Search" @click="search">搜索</el-button>
              <el-button @click="reset">重置筛选</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-alert v-if="salaryError" :title="salaryError" type="error" :closable="false" show-icon class="filter-error" />

      <div v-loading="loading" class="cards">
        <el-empty v-if="!rows.length && !loading" :description="emptyText">
          <el-button v-if="hasFilter" @click="reset">清空筛选条件</el-button>
          <el-button v-else type="primary" @click="router.push('/student/recommend')">看看为你推荐</el-button>
        </el-empty>
        <div v-for="job in rows" :key="job.id" class="job-card" @click="open(job)">
          <div class="job-top">
            <div class="job-main">
              <div class="job-title">{{ job.title }}</div>
              <div class="company">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
            </div>
            <div class="salary">
              {{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}<sup v-if="isEstimatedSalary(job)" title="估算薪资">*</sup>
            </div>
          </div>
          <div class="meta">
            <el-tag size="small">{{ labelOf(EDUCATION, job.education) }}</el-tag>
            <el-tag size="small" type="info">{{ labelOf(JOB_TYPE, job.jobType) }}</el-tag>
            <el-tag v-for="name in (job.tagNames || []).slice(0, 6)" :key="name" size="small" type="success" effect="plain">{{ name }}</el-tag>
            <span class="spacer" />
            <JobSourceTag :job="job" />
            <el-tag v-if="job.applied" size="small" type="primary" effect="dark">已投递</el-tag>
            <el-tag v-else-if="job.favorited" size="small" type="warning">已收藏</el-tag>
          </div>
        </div>
      </div>
      <div class="pager">
        <el-pagination
          v-model:current-page="page.current"
          v-model:page-size="page.size"
          :total="page.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCategories, searchJobs } from '@/api/public'
import JobSourceTag from '@/components/JobSourceTag.vue'
import { EDUCATION, JOB_SOURCE_OPTIONS, JOB_TYPE, isEstimatedSalary, labelOf, salaryText } from '@/utils/job'

const CITIES = ['北京', '上海', '深圳', '广州', '杭州', '成都', '武汉', '南京', '西安', '苏州', '合肥', '长沙']

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const rows = ref([])
const directions = ref([])
const page = reactive({ current: 1, size: 10, total: 0 })
const EMPTY = { keyword: '', techDirection: '', city: '', salaryMin: null, salaryMax: null, education: null, jobType: null, source: '', sort: 'newest' }
const query = reactive({ ...EMPTY })

const salaryError = computed(() => {
  if (query.salaryMin != null && query.salaryMax != null && query.salaryMin > query.salaryMax) {
    return '最低月薪不能高于最高月薪'
  }
  return ''
})
const hasFilter = computed(() => Object.keys(EMPTY).some((k) => k !== 'sort' && query[k] !== EMPTY[k] && query[k] !== undefined))
const emptyText = computed(() => (hasFilter.value ? '没有符合条件的职位，试试放宽筛选条件' : '暂时没有在招职位'))

function leafNames(nodes, acc = []) {
  for (const node of nodes || []) {
    if (node.children && node.children.length) leafNames(node.children, acc)
    else acc.push(node.name)
  }
  return acc
}

function toNumber(v) {
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** 从地址栏恢复筛选条件，返回职位详情后条件不丢 */
function readQuery() {
  const q = route.query
  query.keyword = q.keyword || ''
  query.techDirection = q.techDirection || ''
  query.city = q.city || ''
  query.salaryMin = toNumber(q.salaryMin)
  query.salaryMax = toNumber(q.salaryMax)
  query.education = toNumber(q.education)
  query.jobType = toNumber(q.jobType)
  query.source = q.source || ''
  query.sort = q.sort || 'newest'
  page.current = toNumber(q.page) || 1
  page.size = toNumber(q.size) || 10
}

function params() {
  return {
    keyword: query.keyword.trim() || undefined,
    techDirection: query.techDirection || undefined,
    city: (query.city || '').trim() || undefined,
    salaryMin: query.salaryMin || undefined,
    salaryMax: query.salaryMax || undefined,
    education: query.education || undefined,
    jobType: query.jobType || undefined,
    source: query.source || undefined,
    sort: query.sort !== 'newest' ? query.sort : undefined
  }
}

async function load() {
  if (salaryError.value) return
  const p = params()
  router.replace({ query: { ...p, page: page.current > 1 ? page.current : undefined, size: page.size !== 10 ? page.size : undefined } })
  loading.value = true
  try {
    const res = await searchJobs({ ...p, sort: query.sort, current: page.current, size: page.size })
    rows.value = res.records || []
    page.total = res.total || 0
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function search() {
  page.current = 1
  load()
}

function reset() {
  Object.assign(query, EMPTY)
  search()
}

function open(job) {
  router.push(`/student/jobs/${job.id}`)
}

onMounted(async () => {
  readQuery()
  load()
  try {
    directions.value = leafNames(await getCategories())
  } catch {
    directions.value = []
  }
})
</script>

<style scoped>
.filters :deep(.el-form-item) { margin-bottom: 12px; }
.filters :deep(.el-select),
.filters :deep(.el-input-number) { width: 100%; }
.salary-range { display: flex; align-items: center; gap: 6px; width: 100%; }
.salary-range :deep(.el-input-number) { flex: 1; }
.dash { color: var(--el-text-color-secondary); }
.filter-actions :deep(.el-form-item__content) { justify-content: flex-end; }
.filter-error { margin-bottom: 12px; }
.cards { min-height: 120px; }
.job-card {
  padding: 14px 16px;
  margin-bottom: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.job-card:hover { border-color: var(--el-color-primary-light-5); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06); }
.job-top { display: flex; justify-content: space-between; gap: 12px; }
.job-main { min-width: 0; }
.job-title { font-size: 16px; font-weight: 600; color: #1a202c; }
.company { color: var(--el-text-color-secondary); margin-top: 4px; font-size: 13px; }
.salary { color: #e67e22; font-weight: 600; white-space: nowrap; }
.salary sup { color: #e6a23c; margin-left: 1px; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; align-items: center; }
.spacer { flex: 1; }
</style>
