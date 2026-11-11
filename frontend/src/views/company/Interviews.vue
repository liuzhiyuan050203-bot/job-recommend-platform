<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <span class="title">面试安排</span>
            <span class="hint head-hint">在「候选人管理」里给候选人发送笔试 / 面试通知后，安排会出现在这里</span>
          </div>
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
          <template #default="{ row }">
            <template v-if="row.interviewType === 1">
              <a v-if="isUrl(row.meetingUrl)" :href="row.meetingUrl" target="_blank" rel="noopener noreferrer">{{ row.meetingUrl }}</a>
              <span v-else>{{ row.meetingUrl || '未填写链接' }}</span>
            </template>
            <span v-else>{{ row.location || '未填写地点' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="['warning', 'success', 'info', 'danger'][row.interviewStatus] || 'info'">{{ row.interviewStatusName }}</el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" description="暂无面试安排">
            <el-button type="primary" @click="router.push('/company/candidates')">去候选人管理发送通知</el-button>
          </el-empty>
        </template>
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

    <el-dialog v-model="visible" title="记录面试结果" width="460px">
      <el-alert v-if="current" type="info" :closable="false" class="target">
        <template #title>{{ current.studentName }} · {{ current.jobTitle }} · {{ current.roundName }}（{{ current.interviewTime }}）</template>
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="结果">
          <el-select v-model="result.interviewStatus" style="width: 100%">
            <el-option v-for="item in INTERVIEW_STATUS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="result.remark" type="textarea" :rows="3" maxlength="255" show-word-limit placeholder="面试评价、结论或后续安排（选填）" />
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
import { useRouter } from 'vue-router'
import { getCompanyInterviews, saveInterviewResult } from '@/api/company'
import { INTERVIEW_STATUS } from '@/utils/job'

const router = useRouter()
const current = ref(null)
const loading = ref(false)

function isUrl(v) {
  return /^https?:\/\//i.test(v || '')
}
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
  current.value = row
  result.id = row.id
  result.interviewStatus = row.interviewStatus
  result.remark = row.remark || ''
  visible.value = true
}

async function submit() {
  saving.value = true
  try {
    await saveInterviewResult(result.id, { interviewStatus: result.interviewStatus, remark: result.remark })
    ElMessage.success('面试结果已保存')
    visible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head-hint { display: block; margin-top: 4px; }
.target { margin-bottom: 12px; }
.title { font-weight: 600; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
