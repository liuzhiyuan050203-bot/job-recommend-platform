<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">企业资质与入驻审核</span>
          <div class="header-filters">
            <el-select v-model="filterStatus" placeholder="审核状态" clearable style="width: 130px" @change="handleSearch">
              <el-option label="待审核" :value="0" />
              <el-option label="已通过" :value="1" />
              <el-option label="已驳回" :value="2" />
            </el-select>

            <el-input
              v-model="keyword"
              placeholder="搜索企业全称、信用代码或联系人"
              clearable
              style="width: 250px"
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

      <el-table :data="companies" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="companyName" label="企业全称" min-width="180" />
        <el-table-column prop="creditCode" label="统一社会信用代码" min-width="170">
          <template #default="{ row }">
            <code>{{ row.creditCode || '未填写' }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业 / 城市" width="160">
          <template #default="{ row }">
            <span>{{ row.industry || '-' }} / {{ row.city || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="contactName" label="联系人 / 电话" width="160">
          <template #default="{ row }">
            <div>{{ row.contactName || '-' }}</div>
            <div class="sub-text">{{ row.contactPhone || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="auditStatus" label="审核状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.auditStatus === 1 ? 'success' : (row.auditStatus === 2 ? 'danger' : 'warning')">
              {{ row.auditStatus === 1 ? '已通过' : (row.auditStatus === 2 ? '已驳回' : '待审核') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="申请时间" width="160" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">详情/证照</el-button>
            <el-button type="success" link size="small" @click="openAuditDialog(row, 1)">通过</el-button>
            <el-button type="danger" link size="small" @click="openAuditDialog(row, 2)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchCompanies"
          @current-change="fetchCompanies"
        />
      </div>
    </el-card>

    <!-- 资质详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="企业基本资料与资质证照" size="500px">
      <div v-if="currentCompany" class="drawer-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="企业全称">{{ currentCompany.companyName }}</el-descriptions-item>
          <el-descriptions-item label="企业简称">{{ currentCompany.shortName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属行业">{{ currentCompany.industry || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所在省市">{{ currentCompany.province }} {{ currentCompany.city }}</el-descriptions-item>
          <el-descriptions-item label="详细地址">{{ currentCompany.address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="统一信用代码">{{ currentCompany.creditCode || '未登记' }}</el-descriptions-item>
          <el-descriptions-item label="招聘联系人">{{ currentCompany.contactName }} ({{ currentCompany.contactPhone }})</el-descriptions-item>
          <el-descriptions-item label="联系邮箱">{{ currentCompany.contactEmail || '-' }}</el-descriptions-item>
          <el-descriptions-item label="当前审核状态">
            <el-tag :type="currentCompany.auditStatus === 1 ? 'success' : (currentCompany.auditStatus === 2 ? 'danger' : 'warning')">
              {{ currentCompany.auditStatus === 1 ? '已通过' : (currentCompany.auditStatus === 2 ? '已驳回' : '待审核') }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentCompany.auditRemark" label="审核意见">
            {{ currentCompany.auditRemark }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="license-section">
          <h4>营业执照证明材料：</h4>
          <div v-if="currentCompany.licenseUrl">
            <el-image
              :src="currentCompany.licenseUrl"
              fit="contain"
              class="drawer-license-img"
              :preview-src-list="[currentCompany.licenseUrl]"
            />
          </div>
          <el-empty v-else description="暂未上传营业执照图片" />
        </div>

        <div class="drawer-actions">
          <el-button type="success" @click="openAuditDialog(currentCompany, 1)">审核通过</el-button>
          <el-button type="danger" @click="openAuditDialog(currentCompany, 2)">驳回申请</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 审核弹窗 -->
    <el-dialog v-model="auditDialogVisible" :title="auditStatus === 1 ? '资质审核通过确认' : '资质审核驳回'" width="450px">
      <el-form label-width="80px">
        <el-form-item label="审核结果">
          <el-tag :type="auditStatus === 1 ? 'success' : 'danger'" size="large">
            {{ auditStatus === 1 ? '审核通过 (予以开通招聘权限)' : '驳回申请 (要求修改材料)' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input
            v-model="auditRemark"
            type="textarea"
            :rows="3"
            placeholder="填写审核批复意见或驳回原因说明..."
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
import { ElMessage } from 'element-plus'
import { getAdminCompanies, auditAdminCompany } from '@/api/admin'

const loading = ref(false)
const submittingAudit = ref(false)
const companies = ref([])
const filterStatus = ref(0) // 默认展示待审核
const keyword = ref('')

const pagination = reactive({
  current: 1,
  size: 10,
  total: 0
})

const drawerVisible = ref(false)
const currentCompany = ref(null)

const auditDialogVisible = ref(false)
const auditTargetId = ref(null)
const auditStatus = ref(1)
const auditRemark = ref('')

const fetchCompanies = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      auditStatus: filterStatus.value !== null ? filterStatus.value : undefined,
      keyword: keyword.value.trim() || undefined
    }
    const res = await getAdminCompanies(params)
    companies.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchCompanies()
}

const viewDetail = (row) => {
  currentCompany.value = row
  drawerVisible.value = true
}

const openAuditDialog = (row, status) => {
  auditTargetId.value = row.id
  auditStatus.value = status
  auditRemark.value = status === 1 ? '资质材料齐全，符合企业入驻要求，予以通过。' : '营业执照模糊或统一社会信用代码不符，请核对后重新上传。'
  auditDialogVisible.value = true
}

const handleConfirmAudit = async () => {
  submittingAudit.value = true
  try {
    await auditAdminCompany(auditTargetId.value, {
      auditStatus: auditStatus.value,
      auditRemark: auditRemark.value.trim()
    })
    ElMessage.success('审核操作成功')
    auditDialogVisible.value = false
    drawerVisible.value = false
    fetchCompanies()
  } catch (err) {
    console.error(err)
  } finally {
    submittingAudit.value = false
  }
}

onMounted(() => {
  fetchCompanies()
})
</script>

<style scoped>
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
.sub-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
.license-section {
  margin-top: 20px;
}
.license-section h4 {
  font-size: 14px;
  margin-bottom: 8px;
}
.drawer-license-img {
  width: 100%;
  max-height: 240px;
  border-radius: 6px;
  background-color: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
}
.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 30px;
}
</style>
