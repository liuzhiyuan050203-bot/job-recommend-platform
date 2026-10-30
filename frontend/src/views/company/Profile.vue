<template>
  <div class="company-profile-container">
    <!-- 资质审核状态横幅指示 -->
    <el-card shadow="never" class="status-banner" :class="statusCardClass">
      <div class="status-content">
        <div class="status-icon">
          <el-icon v-if="profile.auditStatus === 1" :size="32" color="#67C23A"><CircleCheckFilled /></el-icon>
          <el-icon v-else-if="profile.auditStatus === 2" :size="32" color="#F56C6C"><CircleCloseFilled /></el-icon>
          <el-icon v-else :size="32" color="#E6A23C"><WarningFilled /></el-icon>
        </div>
        <div class="status-text">
          <div class="status-title">
            企业资质认证状态：
            <el-tag :type="statusTagType" effect="dark" size="large">
              {{ statusLabel }}
            </el-tag>
          </div>
          <div class="status-desc">
            <template v-if="profile.auditStatus === 1">
              企业资质已通过平台管理员认证，您可正常发布招聘职位、筛选候选人投递与安排面试日程。
            </template>
            <template v-else-if="profile.auditStatus === 2">
              资质审核已被管理员驳回。<b>驳回原因：{{ profile.auditRemark || '资料不全或证照不符，请重新核对提交。' }}</b>
            </template>
            <template v-else>
              资质材料已提交，目前正在由平台管理员审核中。审核通过前，职位发布与简历筛选功能暂未开放。
            </template>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20">
      <!-- 基本信息编辑 -->
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="box-card" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><OfficeBuilding /></el-icon> 企业基本信息</span>
              <el-button type="primary" :loading="savingInfo" @click="handleSaveInfo">
                保存基本资料
              </el-button>
            </div>
          </template>

          <el-form
            ref="infoFormRef"
            :model="infoForm"
            :rules="infoRules"
            label-width="110px"
            label-position="right"
          >
            <el-form-item label="企业全称" prop="companyName">
              <el-input v-model="infoForm.companyName" placeholder="如：星澜科技有限公司" />
            </el-form-item>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="企业简称" prop="shortName">
                  <el-input v-model="infoForm.shortName" placeholder="如：星澜科技" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="所属行业" prop="industry">
                  <el-select v-model="infoForm.industry" placeholder="选择所属行业" filterable allow-create style="width: 100%">
                    <el-option label="互联网/IT/软件" value="互联网/IT/软件" />
                    <el-option label="人工智能/大数据" value="人工智能/大数据" />
                    <el-option label="金融科技" value="金融科技" />
                    <el-option label="电子商务" value="电子商务" />
                    <el-option label="智能硬件/物联网" value="智能硬件/物联网" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="人员规模" prop="scale">
                  <el-select v-model="infoForm.scale" placeholder="选择规模" style="width: 100%">
                    <el-option label="20人以下" :value="1" />
                    <el-option label="20-99人" :value="2" />
                    <el-option label="100-499人" :value="3" />
                    <el-option label="500-999人" :value="4" />
                    <el-option label="1000-9999人" :value="5" />
                    <el-option label="10000人以上" :value="6" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="徽标 Logo URL">
                  <el-input v-model="infoForm.logoUrl" placeholder="输入企业 Logo 图片链接" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="所在省份" prop="province">
                  <el-input v-model="infoForm.province" placeholder="如：浙江、广东、北京" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="所在城市" prop="city">
                  <el-input v-model="infoForm.city" placeholder="如：杭州、深圳" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="详细办公地址" prop="address">
              <el-input v-model="infoForm.address" placeholder="街道门牌号及写字楼楼层" />
            </el-form-item>

            <el-form-item label="官方网站">
              <el-input v-model="infoForm.website" placeholder="如：https://example.com" />
            </el-form-item>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="8">
                <el-form-item label="招聘联系人" prop="contactName">
                  <el-input v-model="infoForm.contactName" placeholder="如：李HR" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="联系电话" prop="contactPhone">
                  <el-input v-model="infoForm.contactPhone" placeholder="手机或座机" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="联系邮箱" prop="contactEmail">
                  <el-input v-model="infoForm.contactEmail" placeholder="HR邮箱" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="企业介绍" prop="intro">
              <el-input
                v-model="infoForm.intro"
                type="textarea"
                :rows="4"
                placeholder="介绍企业业务、发展历程、技术实力与雇主品牌优势..."
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 资质审核提交 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="box-card" v-loading="loading">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><Stamp /></el-icon> 营业执照与资质认证</span>
              <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
            </div>
          </template>

          <el-alert
            title="资质提交说明"
            type="info"
            :closable="false"
            show-icon
            description="根据国家招聘合规要求，请填写真实有效的统一社会信用代码并提供营业执照电子版链接。提交或重新提交后将重新进入待审核流。"
            style="margin-bottom: 20px"
          />

          <el-form
            ref="qualFormRef"
            :model="qualForm"
            :rules="qualRules"
            label-width="110px"
            label-position="top"
          >
            <el-form-item label="统一社会信用代码 (18位)" prop="creditCode">
              <el-input
                v-model="qualForm.creditCode"
                placeholder="如：91330100MA2XXXXX"
                maxlength="18"
              />
            </el-form-item>

            <el-form-item label="营业执照 / 资质证明图片地址 (URL)" prop="licenseUrl">
              <el-input
                v-model="qualForm.licenseUrl"
                placeholder="https://... 或资质图片托管地址"
              />
            </el-form-item>

            <div v-if="qualForm.licenseUrl" class="license-preview">
              <div class="preview-title">营业执照预览：</div>
              <el-image
                :src="qualForm.licenseUrl"
                fit="contain"
                class="license-img"
                :preview-src-list="[qualForm.licenseUrl]"
              >
                <template #error>
                  <div class="image-slot">图片加载失败，请检查 URL</div>
                </template>
              </el-image>
            </div>

            <div class="qual-btn-row">
              <el-button
                type="warning"
                size="large"
                :loading="submittingQual"
                @click="handleSubmitQualification"
                style="width: 100%"
              >
                {{ profile.auditStatus === 1 ? '更新并重新提交资质审核' : '提交资质审核' }}
              </el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCompanyProfile, updateCompanyProfile, submitCompanyQualification } from '@/api/company'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const savingInfo = ref(false)
const submittingQual = ref(false)

const profile = ref({
  auditStatus: 0,
  auditRemark: ''
})

const infoFormRef = ref(null)
const infoForm = reactive({
  companyName: '',
  shortName: '',
  logoUrl: '',
  industry: '',
  scale: 2,
  province: '',
  city: '',
  address: '',
  website: '',
  intro: '',
  contactName: '',
  contactPhone: '',
  contactEmail: ''
})

const infoRules = {
  companyName: [{ required: true, message: '请输入企业全称', trigger: 'blur' }],
  contactName: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contactPhone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }]
}

const qualFormRef = ref(null)
const qualForm = reactive({
  creditCode: '',
  licenseUrl: ''
})

const qualRules = {
  creditCode: [{ required: true, message: '请输入统一社会信用代码', trigger: 'blur' }],
  licenseUrl: [{ required: true, message: '请输入营业执照地址', trigger: 'blur' }]
}

const statusTagType = computed(() => {
  if (profile.value.auditStatus === 1) return 'success'
  if (profile.value.auditStatus === 2) return 'danger'
  return 'warning'
})

const statusLabel = computed(() => {
  if (profile.value.auditStatus === 1) return '审核通过'
  if (profile.value.auditStatus === 2) return '已驳回'
  return '待审核'
})

const statusCardClass = computed(() => {
  if (profile.value.auditStatus === 1) return 'status-success'
  if (profile.value.auditStatus === 2) return 'status-danger'
  return 'status-warning'
})

const fetchProfile = async () => {
  loading.value = true
  try {
    const res = await getCompanyProfile()
    if (res) {
      profile.value = res
      Object.assign(infoForm, {
        companyName: res.companyName || '',
        shortName: res.shortName || '',
        logoUrl: res.logoUrl || '',
        industry: res.industry || '',
        scale: res.scale || 2,
        province: res.province || '',
        city: res.city || '',
        address: res.address || '',
        website: res.website || '',
        intro: res.intro || '',
        contactName: res.contactName || '',
        contactPhone: res.contactPhone || '',
        contactEmail: res.contactEmail || ''
      })
      Object.assign(qualForm, {
        creditCode: res.creditCode || '',
        licenseUrl: res.licenseUrl || ''
      })
      // 同步到 store
      userStore.fetchCurrentUser()
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSaveInfo = async () => {
  if (!infoFormRef.value) return
  await infoFormRef.value.validate(async (valid) => {
    if (!valid) return
    savingInfo.value = true
    try {
      await updateCompanyProfile(infoForm)
      ElMessage.success('基本资料保存成功')
      userStore.fetchCurrentUser()
    } catch (err) {
      console.error(err)
    } finally {
      savingInfo.value = false
    }
  })
}

const handleSubmitQualification = async () => {
  if (!qualFormRef.value) return
  await qualFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      await ElMessageBox.confirm('提交后企业资质将重新进入【待审核】状态，确认提交吗？', '提示', { type: 'warning' })
      submittingQual.value = true
      await submitCompanyQualification({
        companyName: infoForm.companyName,
        creditCode: qualForm.creditCode.trim(),
        licenseUrl: qualForm.licenseUrl.trim()
      })
      ElMessage.success('资质提交成功，请等待管理员审核')
      fetchProfile()
    } catch (err) {
      // cancelled or failed
    } finally {
      submittingQual.value = false
    }
  })
}

onMounted(() => {
  fetchProfile()
})
</script>

<style scoped>
.company-profile-container {
  padding: 10px 0;
}
.status-banner {
  margin-bottom: 20px;
  border-radius: 8px;
}
.status-content {
  display: flex;
  align-items: center;
  gap: 16px;
}
.status-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.status-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}
.status-success {
  background-color: #f0f9eb;
  border-color: #e1f3d8;
}
.status-warning {
  background-color: #fdf6ec;
  border-color: #faecd8;
}
.status-danger {
  background-color: #fef0f0;
  border-color: #fde2e2;
}
.box-card {
  border-radius: 8px;
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-weight: 600;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.license-preview {
  margin-top: 10px;
  margin-bottom: 16px;
}
.preview-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.license-img {
  width: 100%;
  height: 160px;
  background-color: var(--el-fill-color-light);
  border-radius: 6px;
  border: 1px dashed var(--el-border-color);
}
.qual-btn-row {
  margin-top: 20px;
}
</style>
