<template>
  <div class="page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">候选人管理</span>
          <div class="filters">
            <el-select v-model="query.jobId" clearable placeholder="全部职位" style="width: 220px" @change="search">
              <el-option v-for="job in jobs" :key="job.id" :label="job.title" :value="job.id" />
            </el-select>
            <el-select v-model="query.status" clearable placeholder="全部状态" style="width: 140px" @change="search">
              <el-option v-for="item in APP_STATUS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-input v-model="query.keyword" clearable placeholder="姓名或职位" style="width: 200px" @keyup.enter="search" />
            <el-button type="primary" @click="search">筛选</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="jobTitle" label="应聘职位" min-width="160" />
        <el-table-column label="学历" width="160">
          <template #default="{ row }">{{ row.educationName || '-' }} / {{ row.school || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="appTagType(row.status)">{{ row.statusName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updateTime" label="最近更新" width="170" />
        <el-table-column label="操作" min-width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">简历</el-button>
            <el-button
              v-for="next in row.nextStatuses || []"
              :key="next.status"
              link
              :type="next.status === 4 ? 'danger' : 'success'"
              @click="move(row, next)"
            >{{ next.statusName }}</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link @click="openNotice(row, 1)">发笔试</el-button>
            <el-button v-if="row.status === 0 || row.status === 1 || row.status === 2" link @click="openNotice(row, 2)">发面试</el-button>
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

    <el-drawer v-model="drawer" title="候选人与简历" size="560px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="姓名">{{ detail.studentName }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ detail.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学校">{{ detail.school || '-' }} · {{ detail.major || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学历">{{ detail.educationName || '-' }} / {{ detail.graduationYear || '-' }}届</el-descriptions-item>
          <el-descriptions-item label="职位">{{ detail.jobTitle }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.statusName }}</el-descriptions-item>
        </el-descriptions>
        <div class="block">
          <h4>技能</h4>
          <el-tag v-for="skill in detail.skills || []" :key="skill.id" class="tag">{{ skill.tagName }} · {{ skill.proficiency }}</el-tag>
          <span v-if="!(detail.skills || []).length">暂无</span>
        </div>
        <div v-if="detail.resume" class="block">
          <h4>{{ detail.resume.title }}</h4>
          <p><b>教育经历</b>{{ detail.resume.educationExp || '无' }}</p>
          <p><b>项目经历</b>{{ detail.resume.projectExp || '无' }}</p>
          <p><b>实习经历</b>{{ detail.resume.internshipExp || '无' }}</p>
          <p><b>技能概述</b>{{ detail.resume.skillDesc || '无' }}</p>
          <p><b>自我评价</b>{{ detail.resume.selfEvaluation || '无' }}</p>
        </div>
        <div class="block">
          <h4>状态日志</h4>
          <el-timeline>
            <el-timeline-item v-for="log in detail.logs || []" :key="log.id" :timestamp="log.createTime">
              {{ log.fromStatusName || '新建' }} → {{ log.toStatusName }}（{{ log.operatorName || '系统' }}）
              <div v-if="log.remark">{{ log.remark }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="noticeVisible" :title="notice.noticeType === 1 ? '发送笔试通知' : '发送面试通知'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="时间">
          <el-date-picker v-model="notice.interviewTime" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="方式">
          <el-radio-group v-model="notice.interviewType">
            <el-radio :value="1">线上</el-radio>
            <el-radio :value="2">线下</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="notice.interviewType === 2" label="地点">
          <el-input v-model="notice.location" />
        </el-form-item>
        <el-form-item v-else label="链接">
          <el-input v-model="notice.meetingUrl" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="notice.contactName" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="notice.contactPhone" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="notice.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noticeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitNotice">发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCompanyApplication, getCompanyApplications, getCompanyJobs, sendInterviewNotice, updateApplicationStatus } from '@/api/company'
import { APP_STATUS, appTagType } from '@/utils/job'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const jobs = ref([])
const drawer = ref(false)
const detail = ref(null)
const noticeVisible = ref(false)
const query = reactive({ jobId: null, status: null, keyword: '' })
const page = reactive({ current: 1, size: 10, total: 0 })
const notice = reactive({
  applicationId: null,
  noticeType: 2,
  interviewTime: '',
  interviewType: 1,
  location: '',
  meetingUrl: '',
  contactName: '',
  contactPhone: '',
  remark: ''
})

async function load() {
  loading.value = true
  try {
    const res = await getCompanyApplications({
      current: page.current,
      size: page.size,
      jobId: query.jobId || undefined,
      status: query.status === null || query.status === '' ? undefined : query.status,
      keyword: query.keyword.trim() || undefined
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

async function openDetail(row) {
  detail.value = await getCompanyApplication(row.id)
  drawer.value = true
}

async function move(row, next) {
  const { value } = await ElMessageBox.prompt(`将状态变更为「${next.statusName}」`, '状态流转', {
    inputPlaceholder: '备注，可空',
    inputValue: ''
  })
  await updateApplicationStatus(row.id, { toStatus: next.status, remark: value || '' })
  ElMessage.success('状态已更新')
  load()
}

function openNotice(row, noticeType) {
  notice.applicationId = row.id
  notice.noticeType = noticeType
  notice.interviewType = 1
  notice.location = ''
  notice.meetingUrl = ''
  notice.remark = noticeType === 1 ? '请准时参加笔试' : '请准时参加面试'
  noticeVisible.value = true
}

async function submitNotice() {
  if (!notice.interviewTime) {
    ElMessage.warning('请选择时间')
    return
  }
  saving.value = true
  try {
    await sendInterviewNotice(notice.applicationId, { ...notice, applicationId: undefined })
    ElMessage.success('通知已发送')
    noticeVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const res = await getCompanyJobs({ current: 1, size: 100 })
  jobs.value = res.records || []
  load()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center; }
.title { font-weight: 600; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
.block { margin-top: 16px; }
.block p { white-space: pre-wrap; line-height: 1.6; }
.tag { margin: 0 6px 6px 0; }
</style>
