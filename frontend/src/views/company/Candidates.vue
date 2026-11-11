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
            <el-input v-model="query.keyword" clearable placeholder="姓名或职位" style="width: 200px" @keyup.enter="search" @clear="search" />
            <el-button type="primary" @click="search">筛选</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="rows" stripe @sort-change="onSortChange">
        <el-table-column prop="studentName" label="姓名" width="100" />
        <el-table-column prop="jobTitle" label="应聘职位" min-width="160" />
        <el-table-column label="学历" width="160">
          <template #default="{ row }">{{ row.educationName || '-' }} / {{ row.school || '-' }}</template>
        </el-table-column>
        <el-table-column label="技能（熟练度）" min-width="260">
          <template #default="{ row }">
            <SkillChips :skills="row.candidateSkills" :limit="5" />
          </template>
        </el-table-column>
        <el-table-column prop="matchScore" label="匹配分" width="110" sortable="custom">
          <template #default="{ row }">
            <el-tooltip v-if="row.matchScore !== null && row.matchScore !== undefined" placement="top"
              :content="matchTip(row)">
              <span :class="['score', scoreClass(row.matchScore)]">{{ row.matchScore }}</span>
            </el-tooltip>
            <el-tooltip v-else content="该职位没有设置技能标签，无法计算匹配分" placement="top">
              <span class="muted">—</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="appTagType(row.status)">{{ row.statusName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updateTime" label="最近更新" width="170" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看简历</el-button>
            <el-dropdown v-if="(row.nextStatuses || []).length" trigger="click" @command="(next) => move(row, next)">
              <el-button link type="success">推进状态<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="next in row.nextStatuses" :key="next.status" :command="next">
                    <span :class="{ danger: next.status === 4 }">标记为「{{ next.statusName }}」</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-dropdown v-if="row.status <= 2" trigger="click" @command="(type) => openNotice(row, type)">
              <el-button link>发通知<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="row.status <= 1" :command="1">笔试通知</el-dropdown-item>
                  <el-dropdown-item :command="2">面试通知</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" :description="query.jobId || (query.status !== null && query.status !== undefined && query.status !== '') || query.keyword ? '没有符合筛选条件的候选人' : '还没有收到投递，职位审核通过并上架后学生即可投递'" />
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

    <el-drawer v-model="drawer" title="候选人与简历" size="560px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="姓名">{{ detail.studentName }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ detail.phone || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学校">{{ detail.school || '-' }} · {{ detail.major || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学历">{{ detail.educationName || '-' }} / {{ detail.graduationYear || '-' }}届</el-descriptions-item>
          <el-descriptions-item label="职位">{{ detail.jobTitle }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="appTagType(detail.status)">{{ detail.statusName }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        <div class="drawer-actions">
          <el-button
            v-for="next in detail.nextStatuses || []"
            :key="next.status"
            size="small"
            :type="next.status === 4 ? 'danger' : 'success'"
            plain
            @click="move(detail, next)"
          >{{ next.statusName }}</el-button>
          <el-button v-if="detail.status === 0 || detail.status === 1" size="small" @click="openNotice(detail, 1)">发笔试</el-button>
          <el-button v-if="detail.status === 0 || detail.status === 1 || detail.status === 2" size="small" @click="openNotice(detail, 2)">发面试</el-button>
        </div>
        <div class="block">
          <h4>
            技能匹配
            <span v-if="detail.matchScore !== null && detail.matchScore !== undefined" :class="['score', scoreClass(detail.matchScore)]">
              {{ detail.matchScore }} 分
            </span>
            <span class="muted small">{{ matchTip(detail) }}</span>
          </h4>
          <SkillChips :skills="detail.candidateSkills" />
          <div v-if="(detail.missingSkills || []).length" class="missing">
            职位要求但未掌握：
            <el-tag v-for="name in detail.missingSkills" :key="name" type="info" effect="plain" size="small" class="tag">{{ name }}</el-tag>
          </div>
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
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCompanyApplication, getCompanyApplications, getCompanyJobs, sendInterviewNotice, updateApplicationStatus } from '@/api/company'
import { APP_STATUS, appTagType } from '@/utils/job'
import SkillChips from '@/components/SkillChips.vue'

const route = useRoute()
const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const jobs = ref([])
const drawer = ref(false)
const detail = ref(null)
const noticeVisible = ref(false)
const query = reactive({ jobId: null, status: null, keyword: '', sort: undefined })
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
      keyword: query.keyword.trim() || undefined,
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

async function openDetail(row) {
  detail.value = await getCompanyApplication(row.id)
  drawer.value = true
}

// 列表里改了状态或发了通知后，如果抽屉正开着同一个候选人，就重新拉详情，避免状态和日志停留在旧值
async function refreshAfterChange(applicationId) {
  const tasks = [load()]
  if (drawer.value && detail.value?.id === applicationId) {
    tasks.push(getCompanyApplication(applicationId).then((res) => { detail.value = res }))
  }
  await Promise.all(tasks)
}

function onSortChange({ prop, order }) {
  query.sort = prop === 'matchScore' && order ? (order === 'ascending' ? 'matchAsc' : 'matchDesc') : undefined
  search()
}

function scoreClass(score) {
  if (score >= 80) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

function matchTip(row) {
  if (!row || row.jobSkillCount === null || row.jobSkillCount === undefined) return ''
  if (!row.jobSkillCount) return '该职位没有设置技能标签，不计算匹配分'
  return `命中职位技能 ${row.matchedSkillCount}/${row.jobSkillCount}，按熟练度加权（入门 0.6 … 精通 1.0）`
}

async function move(row, next) {
  let value = ''
  try {
    ;({ value } = await ElMessageBox.prompt(`将「${row.studentName || '该候选人'}」的状态变更为「${next.statusName}」`, '状态流转', {
      inputPlaceholder: '备注（可空），学生可在投递详情中看到',
      inputValue: '',
      confirmButtonText: '确认变更',
      cancelButtonText: '取消'
    }))
  } catch {
    return
  }
  await updateApplicationStatus(row.id, { toStatus: next.status, remark: value || '' })
  ElMessage.success('状态已更新')
  await refreshAfterChange(row.id)
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
    await refreshAfterChange(notice.applicationId)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  // 支持从工作台 / 职位管理带条件跳转：?status=0 或 ?jobId=xx
  if (route.query.status !== undefined && route.query.status !== '') query.status = Number(route.query.status)
  if (route.query.jobId) query.jobId = Number(route.query.jobId)
  load()
  try {
    const res = await getCompanyJobs({ current: 1, size: 100 })
    jobs.value = res.records || []
  } catch {
    jobs.value = []
  }
})
</script>

<style scoped>
.danger { color: var(--el-color-danger); }
:deep(.el-dropdown) { vertical-align: middle; margin-left: 10px; }
.card-header { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: center; }
.title { font-weight: 600; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
.block { margin-top: 16px; }
.block p { white-space: pre-wrap; line-height: 1.6; }
.tag { margin: 0 6px 6px 0; }
.drawer-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.block h4 { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.score { font-weight: 600; }
.score.high { color: var(--el-color-success); }
.score.mid { color: var(--el-color-warning); }
.score.low { color: var(--el-color-danger); }
.muted { color: var(--el-text-color-secondary); }
.small { font-size: 12px; font-weight: normal; }
.missing { margin-top: 8px; font-size: 13px; color: var(--el-text-color-secondary); }
</style>
