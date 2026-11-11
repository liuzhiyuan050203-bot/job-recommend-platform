<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">企业招聘职位合规审核</span>
          <div class="header-filters">
            <el-select v-model="filterStatus" placeholder="审核状态" clearable style="width: 130px" @change="handleSearch">
              <el-option label="待审核" :value="0" />
              <el-option label="已通过" :value="1" />
              <el-option label="已驳回" :value="2" />
            </el-select>
            <el-select v-model="filterSource" placeholder="数据来源" clearable style="width: 130px" @change="handleSearch">
              <el-option label="企业发布" value="platform" />
              <el-option label="校招官网同步" value="self_crawl" />
              <el-option label="外部来源" value="ext_ats" />
            </el-select>
            <el-select v-model="filterShelf" placeholder="上下架" clearable style="width: 120px" @change="handleSearch">
              <el-option label="已上架" :value="1" />
              <el-option label="已下架" :value="0" />
            </el-select>

            <el-input
              v-model="keyword"
              placeholder="搜索职位标题、方向或城市"
              clearable
              style="width: 240px"
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #append>
                <el-button icon="Search" @click="handleSearch" />
              </template>
            </el-input>
          </div>
        </div>
      </template>

      <el-table :data="jobs" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="职位名称" min-width="160" />
        <el-table-column prop="companyName" label="发布企业" min-width="150" />
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag v-if="sourceMeta(row.sourceCode)" size="small" :type="sourceMeta(row.sourceCode).type" effect="plain">{{ sourceMeta(row.sourceCode).short }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="techDirection" label="技术方向" width="120">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.techDirection }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="工作地点" width="130">
          <template #default="{ row }">
            <span>{{ row.province }} · {{ row.city }}</span>
          </template>
        </el-table-column>
        <el-table-column label="薪资区间" width="140">
          <template #default="{ row }">
            <span class="salary-text">{{ salaryText(row.salaryMin, row.salaryMax, row.salaryMonths) }}</span>
            <el-tooltip v-if="sourceMeta(row.sourceCode)?.estimated" content="官网未公布薪资，为平台估算" placement="top">
              <sup class="est">估</sup>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="auditStatus" label="审核状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.auditStatus === 1 ? 'success' : (row.auditStatus === 2 ? 'danger' : 'warning')">
              {{ row.auditStatus === 1 ? '通过' : (row.auditStatus === 2 ? '驳回' : '待审') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="shelfStatus" label="货架状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.shelfStatus === 1 ? 'primary' : 'info'" size="small">
              {{ row.shelfStatus === 1 ? '上架' : '下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情</el-button>
            <el-button type="success" link size="small" @click="openAuditDialog(row, 1)">通过</el-button>
            <el-button type="danger" link size="small" @click="openAuditDialog(row, 2)">驳回</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" :description="filterStatus === 0 ? '没有待审核的职位，可切换审核状态查看全部' : '没有符合条件的职位'" />
        </template>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchJobs"
          @current-change="fetchJobs"
        />
      </div>
    </el-card>

    <!-- 职位详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="职位详细描述与要求" size="520px">
      <div v-if="currentJob" class="drawer-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="职位名称">{{ currentJob.title }}</el-descriptions-item>
          <el-descriptions-item label="发布企业">{{ currentJob.companyName }}</el-descriptions-item>
          <el-descriptions-item label="分类目录">{{ currentJob.categoryName }} ({{ currentJob.techDirection }})</el-descriptions-item>
          <el-descriptions-item label="工作地点">{{ currentJob.province }} · {{ currentJob.city }} {{ currentJob.district || '' }}</el-descriptions-item>
          <el-descriptions-item label="薪资待遇">
            {{ currentJob.salaryMin }} - {{ currentJob.salaryMax }} 元/月 ({{ currentJob.salaryMonths }}个月)
          </el-descriptions-item>
          <el-descriptions-item label="招聘人数">{{ currentJob.headcount }} 人</el-descriptions-item>
          <el-descriptions-item label="福利待遇">{{ currentJob.welfare || '无' }}</el-descriptions-item>
          <el-descriptions-item label="当前审核状态">
            <el-tag :type="currentJob.auditStatus === 1 ? 'success' : (currentJob.auditStatus === 2 ? 'danger' : 'warning')">
              {{ currentJob.auditStatus === 1 ? '通过' : (currentJob.auditStatus === 2 ? '驳回' : '待审核') }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentJob.auditRemark" label="审核意见">
            {{ currentJob.auditRemark }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="job-text-block">
          <h4>岗位职责：</h4>
          <ol v-if="parseJobText(currentJob.description).length" class="job-items">
            <li v-for="(item, idx) in parseJobText(currentJob.description)" :key="idx">{{ item }}</li>
          </ol>
          <p v-else>暂无描述</p>
        </div>

        <div class="job-text-block">
          <h4>任职要求：</h4>
          <ol v-if="parseJobText(currentJob.requirement).length" class="job-items">
            <li v-for="(item, idx) in parseJobText(currentJob.requirement)" :key="idx">{{ item }}</li>
          </ol>
          <p v-else>暂无要求</p>
        </div>

        <div class="drawer-actions">
          <el-button type="success" @click="openAuditDialog(currentJob, 1)">审核通过</el-button>
          <el-button type="danger" @click="openAuditDialog(currentJob, 2)">驳回职位</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 审核弹窗 -->
    <el-dialog v-model="auditDialogVisible" :title="auditStatus === 1 ? '职位审核通过' : '职位审核驳回'" width="450px">
      <el-form label-width="80px">
        <el-form-item label="审核结果">
          <el-tag :type="auditStatus === 1 ? 'success' : 'danger'" size="large">
            {{ auditStatus === 1 ? '审核通过 (允许上架公开展示)' : '驳回职位 (需重新修改)' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input
            v-model="auditRemark"
            type="textarea"
            :rows="3"
            placeholder="填写审核批复意见或合规整改说明..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="auditDialogVisible = false">取消</el-button>
          <el-button :type="auditStatus === 1 ? 'success' : 'danger'" :loading="submittingAudit" @click="handleConfirmAudit">
            确认操作
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { salaryText, sourceMeta } from '@/utils/job'
import { ElMessage } from 'element-plus'
import { getAdminJobs, auditAdminJob } from '@/api/admin'
import { parseJobText } from '@/utils/jobText'

const loading = ref(false)
const submittingAudit = ref(false)
const jobs = ref([])
const filterStatus = ref(0) // 默认待审
const filterShelf = ref(null)
const filterSource = ref(null)
const route = useRoute()
const keyword = ref('')

const pagination = reactive({
  current: 1,
  size: 10,
  total: 0
})

const drawerVisible = ref(false)
const currentJob = ref(null)

const auditDialogVisible = ref(false)
const auditTargetId = ref(null)
const auditStatus = ref(1)
const auditRemark = ref('')

const fetchJobs = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      auditStatus: filterStatus.value !== null && filterStatus.value !== '' ? filterStatus.value : undefined,
      shelfStatus: filterShelf.value !== null && filterShelf.value !== '' ? filterShelf.value : undefined,
      source: filterSource.value || undefined,
      keyword: keyword.value.trim() || undefined
    }
    const res = await getAdminJobs(params)
    jobs.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchJobs()
}

const viewDetail = (row) => {
  currentJob.value = row
  drawerVisible.value = true
}

const openAuditDialog = (row, status) => {
  auditTargetId.value = row.id
  auditStatus.value = status
  auditRemark.value = status === 1 ? '岗位职责清晰合规，符合校招招聘发布标准。' : '岗位描述不合规或薪资区间异常，请调整后重新提交。'
  auditDialogVisible.value = true
}

const handleConfirmAudit = async () => {
  submittingAudit.value = true
  try {
    await auditAdminJob(auditTargetId.value, {
      auditStatus: auditStatus.value,
      auditRemark: auditRemark.value.trim()
    })
    ElMessage.success('职位审核操作成功')
    auditDialogVisible.value = false
    drawerVisible.value = false
    fetchJobs()
  } catch (err) {
    console.error(err)
  } finally {
    submittingAudit.value = false
  }
}

onMounted(() => {
  // 支持从管理首页带筛选条件跳转：/admin/jobs?source=ext_ats 或 ?auditStatus=0
  if (route.query.source) {
    filterSource.value = String(route.query.source)
    filterStatus.value = null
  }
  if (route.query.auditStatus !== undefined && route.query.auditStatus !== '') {
    filterStatus.value = Number(route.query.auditStatus)
  }
  fetchJobs()
})
</script>

<style scoped>
.job-items { margin: 0; padding-left: 22px; line-height: 1.8; }
.est { color: #e6a23c; margin-left: 2px; cursor: help; }
.page-container {
  padding: 10px 0;
}
.table-card {
  border-radius: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.title {
  font-weight: 600;
  font-size: 16px;
}
.header-filters {
  display: flex;
  align-items: center;
  gap: 10px;
}
.salary-text {
  font-weight: 600;
  color: #ff6600;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.job-text-block {
  margin-top: 16px;
}
.job-text-block h4 {
  font-size: 14px;
  margin-bottom: 6px;
}
.job-text-block p {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  white-space: pre-wrap;
  background-color: var(--el-fill-color-lighter);
  padding: 10px;
  border-radius: 6px;
}
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 30px;
}
</style>
