<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">面试安排</span>
          <el-select v-model="status" clearable placeholder="全部状态" style="width: 140px" @change="search">
            <el-option v-for="item in INTERVIEW_STATUS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="interviewTime" label="时间" width="170" />
        <el-table-column prop="roundName" label="轮次" width="120" />
        <el-table-column prop="studentName" label="学生" width="100" />
        <el-table-column prop="jobTitle" label="职位" min-width="160" />
        <el-table-column label="方式" width="80">
          <template #default="{ row }">{{ row.interviewTypeName }}</template>
        </el-table-column>
        <el-table-column label="地点 / 链接" min-width="180">
          <template #default="{ row }">{{ row.interviewType === 1 ? row.meetingUrl : row.location }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ row.interviewStatusName }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openResult(row)">记录结果</el-button>
          </template>
        </el-table-column>
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

    <el-dialog v-model="visible" title="记录面试结果" width="420px">
      <el-form label-width="80px">
        <el-form-item label="结果">
          <el-select v-model="result.interviewStatus" style="width: 100%">
            <el-option v-for="item in INTERVIEW_STATUS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="result.remark" type="textarea" />
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
import { ElMessage } from 'element-plus'
import { getCompanyInterviews, saveInterviewResult } from '@/api/company'
import { INTERVIEW_STATUS } from '@/utils/job'

const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const status = ref(null)
const rows = ref([])
const page = reactive({ current: 1, size: 10, total: 0 })
const result = reactive({ id: null, interviewStatus: 1, remark: '' })

async function load() {
  loading.value = true
  try {
    const res = await getCompanyInterviews({
      current: page.current,
      size: page.size,
      interviewStatus: status.value === null || status.value === '' ? undefined : status.value
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

function openResult(row) {
  result.id = row.id
  result.interviewStatus = row.interviewStatus
  result.remark = row.remark || ''
  visible.value = true
}

async function submit() {
  saving.value = true
  try {
    await saveInterviewResult(result.id, { interviewStatus: result.interviewStatus, remark: result.remark })
    ElMessage.success('已记录')
    visible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 600; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
