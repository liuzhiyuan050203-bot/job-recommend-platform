<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header><span class="title">职位搜索</span></template>
      <el-form :inline="true" class="filters">
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" clearable placeholder="职位或企业" style="width: 180px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="技术方向">
          <el-select v-model="query.techDirection" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="item in directions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="城市">
          <el-input v-model="query.city" clearable placeholder="如深圳" style="width: 120px" />
        </el-form-item>
        <el-form-item label="月薪">
          <el-input-number v-model="query.salaryMin" :min="0" :step="1000" placeholder="最低" />
          <span class="dash">-</span>
          <el-input-number v-model="query.salaryMax" :min="0" :step="1000" placeholder="最高" />
        </el-form-item>
        <el-form-item label="学历">
          <el-select v-model="query.education" clearable placeholder="不限" style="width: 120px">
            <el-option v-for="item in EDUCATION.filter((e) => e.value > 0)" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-select v-model="query.sort" style="width: 120px">
            <el-option label="最新" value="newest" />
            <el-option label="薪资" value="salary" />
            <el-option label="热度" value="hot" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
        </el-form-item>
      </el-form>

      <div v-loading="loading" class="cards">
        <el-empty v-if="!rows.length && !loading" description="没有符合条件的职位" />
        <el-card v-for="job in rows" :key="job.id" class="job-card" shadow="hover" @click="open(job)">
          <div class="job-top">
            <div>
              <div class="job-title">{{ job.title }}</div>
              <div class="company">{{ job.companyName }} · {{ job.city }} · {{ job.techDirection }}</div>
            </div>
            <div class="salary">{{ salaryText(job.salaryMin, job.salaryMax, job.salaryMonths) }}</div>
          </div>
          <div class="meta">
            <el-tag size="small">{{ labelOf(EDUCATION, job.education) }}</el-tag>
            <el-tag size="small" type="info">{{ labelOf(JOB_TYPE, job.jobType) }}</el-tag>
            <el-tag v-for="name in job.tagNames || []" :key="name" size="small" type="success">{{ name }}</el-tag>
            <el-tag v-if="job.favorited" size="small" type="warning">已收藏</el-tag>
          </div>
        </el-card>
      </div>
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
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCategories, searchJobs } from '@/api/public'
import { EDUCATION, JOB_TYPE, labelOf, salaryText } from '@/utils/job'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const directions = ref([])
const page = reactive({ current: 1, size: 10, total: 0 })
const query = reactive({
  keyword: '',
  techDirection: '',
  city: '',
  salaryMin: null,
  salaryMax: null,
  education: null,
  sort: 'newest'
})

function leafNames(nodes, acc = []) {
  for (const node of nodes || []) {
    if (node.children && node.children.length) leafNames(node.children, acc)
    else acc.push(node.name)
  }
  return acc
}

async function load() {
  loading.value = true
  try {
    const res = await searchJobs({
      current: page.current,
      size: page.size,
      keyword: query.keyword.trim() || undefined,
      techDirection: query.techDirection || undefined,
      city: query.city.trim() || undefined,
      salaryMin: query.salaryMin || undefined,
      salaryMax: query.salaryMax || undefined,
      education: query.education || undefined,
      sort: query.sort
    })
    rows.value = res.records || []
    page.total = res.total || 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.current = 1
  load()
}

function open(job) {
  router.push(`/student/jobs/${job.id}`)
}

onMounted(async () => {
  const tree = await getCategories()
  directions.value = leafNames(tree)
  load()
})
</script>

<style scoped>
.title { font-weight: 600; }
.filters { margin-bottom: 8px; }
.dash { margin: 0 6px; }
.job-card { margin-bottom: 12px; cursor: pointer; }
.job-top { display: flex; justify-content: space-between; gap: 12px; }
.job-title { font-size: 16px; font-weight: 600; }
.company { color: var(--el-text-color-secondary); margin-top: 4px; }
.salary { color: #e67e22; font-weight: 600; white-space: nowrap; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.pager { display: flex; justify-content: flex-end; margin-top: 8px; }
</style>
