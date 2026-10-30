<template>
  <div class="student-profile-container">
    <el-row :gutter="20">
      <!-- 左侧：基本档案表单 -->
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="box-card" v-loading="profileLoading">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><User /></el-icon> 求职基本档案</span>
              <el-button type="primary" :loading="savingProfile" @click="handleSaveProfile">
                保存基本档案
              </el-button>
            </div>
          </template>

          <el-form
            ref="profileFormRef"
            :model="profileForm"
            :rules="profileRules"
            label-width="100px"
            label-position="right"
          >
            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="真实姓名" prop="realName">
                  <el-input v-model="profileForm.realName" placeholder="如：陈晓" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="性别" prop="gender">
                  <el-radio-group v-model="profileForm.gender">
                    <el-radio :value="1">男</el-radio>
                    <el-radio :value="2">女</el-radio>
                    <el-radio :value="0">保密</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="出生日期" prop="birthday">
                  <el-date-picker
                    v-model="profileForm.birthday"
                    type="date"
                    placeholder="选择出生日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学号" prop="studentNo">
                  <el-input v-model="profileForm.studentNo" placeholder="如：20220101" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="毕业院校" prop="school">
                  <el-input v-model="profileForm.school" placeholder="如：浙江大学" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="所在学院" prop="college">
                  <el-input v-model="profileForm.college" placeholder="如：计算机科学与技术学院" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="所学专业" prop="major">
                  <el-input v-model="profileForm.major" placeholder="如：软件工程" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="学历阶段" prop="education">
                  <el-select v-model="profileForm.education" placeholder="请选择学历" style="width: 100%">
                    <el-option label="专科" :value="1" />
                    <el-option label="本科" :value="2" />
                    <el-option label="硕士" :value="3" />
                    <el-option label="博士" :value="4" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="毕业年份" prop="graduationYear">
                  <el-input-number
                    v-model="profileForm.graduationYear"
                    :min="2020"
                    :max="2035"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="期望城市" prop="expectCity">
                  <el-input v-model="profileForm.expectCity" placeholder="如：杭州、上海" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="16">
              <el-col :xs="24" :sm="12">
                <el-form-item label="期望方向" prop="expectDirection">
                  <el-select
                    v-model="profileForm.expectDirection"
                    placeholder="选择期望技术方向"
                    filterable
                    allow-create
                    style="width: 100%"
                  >
                    <el-option label="后端开发" value="后端开发" />
                    <el-option label="前端开发" value="前端开发" />
                    <el-option label="数据开发" value="数据开发" />
                    <el-option label="人工智能" value="人工智能" />
                    <el-option label="算法工程" value="算法工程" />
                    <el-option label="测试开发" value="测试开发" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="期望月薪(元)">
                  <div class="salary-range">
                    <el-input-number
                      v-model="profileForm.expectSalaryMin"
                      :min="0"
                      :step="1000"
                      placeholder="下限"
                      controls-position="right"
                      style="width: 48%"
                    />
                    <span>-</span>
                    <el-input-number
                      v-model="profileForm.expectSalaryMax"
                      :min="0"
                      :step="1000"
                      placeholder="上限"
                      controls-position="right"
                      style="width: 48%"
                    />
                  </div>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="个人简介" prop="selfIntro">
              <el-input
                v-model="profileForm.selfIntro"
                type="textarea"
                :rows="4"
                placeholder="简短介绍你的学习背景、技术专长与求职意向..."
                maxlength="800"
                show-word-limit
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：技能标签与熟练度表格 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="box-card" v-loading="skillsLoading">
          <template #header>
            <div class="card-header">
              <span class="card-title"><el-icon><PriceTag /></el-icon> 掌握技能 (供推荐与雷达图)</span>
              <el-button type="success" size="small" icon="Plus" @click="openAddSkillDialog">
                添加技能
              </el-button>
            </div>
          </template>

          <el-table :data="skills" stripe style="width: 100%">
            <el-table-column prop="tagName" label="技能名称" min-width="110">
              <template #default="{ row }">
                <el-tag effect="plain">{{ row.tagName }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="direction" label="方向" width="90">
              <template #default="{ row }">
                <span class="direction-text">{{ row.direction }}</span>
              </template>
            </el-table-column>
            <el-table-column label="熟练度 (1-5)" min-width="140">
              <template #default="{ row }">
                <el-rate
                  v-model="row.proficiency"
                  :max="5"
                  @change="(val) => handleProficiencyChange(row, val)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center">
              <template #default="{ row }">
                <el-button
                  type="danger"
                  link
                  icon="Delete"
                  @click="handleDeleteSkill(row.id)"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加技能弹窗 -->
    <el-dialog v-model="skillDialogVisible" title="添加掌握技能" width="450px" destroy-on-close>
      <el-form ref="skillFormRef" :model="skillForm" :rules="skillRules" label-width="90px">
        <el-form-item label="已有标签">
          <el-select
            v-model="selectedTagId"
            placeholder="从已有标签选择（支持搜索）"
            filterable
            clearable
            style="width: 100%"
            @change="handleSelectExistingTag"
          >
            <el-option
              v-for="tag in systemTags"
              :key="tag.id"
              :label="`${tag.name} (${tag.direction})`"
              :value="tag.id"
            />
          </el-select>
        </el-form-item>

        <el-divider>或自定义新技能</el-divider>

        <el-form-item label="技能名称" prop="tagName">
          <el-input v-model="skillForm.tagName" placeholder="如：Flink / PySpark" />
        </el-form-item>

        <el-form-item label="技术方向" prop="direction">
          <el-select v-model="skillForm.direction" placeholder="选择或输入所属方向" filterable allow-create style="width: 100%">
            <el-option label="后端开发" value="后端开发" />
            <el-option label="前端开发" value="前端开发" />
            <el-option label="数据开发" value="数据开发" />
            <el-option label="人工智能" value="人工智能" />
            <el-option label="算法工程" value="算法工程" />
          </el-select>
        </el-form-item>

        <el-form-item label="熟练度" prop="proficiency">
          <el-rate v-model="skillForm.proficiency" :max="5" show-text :texts="['入门', '掌握', '熟悉', '熟练', '精通']" />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="skillDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="savingSkill" @click="handleConfirmAddSkill">确定添加</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getStudentProfile,
  updateStudentProfile,
  getStudentSkills,
  addStudentSkill,
  updateStudentSkill,
  deleteStudentSkill
} from '@/api/student'
import { getSkillTags } from '@/api/public'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const profileLoading = ref(false)
const savingProfile = ref(false)
const skillsLoading = ref(false)
const savingSkill = ref(false)

const profileFormRef = ref(null)
const profileForm = reactive({
  realName: '',
  gender: 0,
  birthday: null,
  studentNo: '',
  school: '',
  college: '',
  major: '',
  education: 2,
  graduationYear: 2026,
  expectCity: '',
  expectSalaryMin: null,
  expectSalaryMax: null,
  expectDirection: '',
  selfIntro: ''
})

const profileRules = {
  realName: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  education: [{ required: true, message: '请选择学历阶段', trigger: 'change' }],
  graduationYear: [{ required: true, message: '请输入毕业年份', trigger: 'blur' }]
}

const skills = ref([])
const systemTags = ref([])

const skillDialogVisible = ref(false)
const selectedTagId = ref(null)
const skillFormRef = ref(null)
const skillForm = reactive({
  skillTagId: null,
  tagName: '',
  direction: '后端开发',
  proficiency: 3
})

const skillRules = {
  proficiency: [{ required: true, message: '请评定熟练度', trigger: 'change' }]
}

const fetchProfile = async () => {
  profileLoading.value = true
  try {
    const res = await getStudentProfile()
    if (res) {
      Object.assign(profileForm, {
        realName: res.realName || '',
        gender: res.gender ?? 0,
        birthday: res.birthday || null,
        studentNo: res.studentNo || '',
        school: res.school || '',
        college: res.college || '',
        major: res.major || '',
        education: res.education || 2,
        graduationYear: res.graduationYear || 2026,
        expectCity: res.expectCity || '',
        expectSalaryMin: res.expectSalaryMin || null,
        expectSalaryMax: res.expectSalaryMax || null,
        expectDirection: res.expectDirection || '',
        selfIntro: res.selfIntro || ''
      })
    }
  } catch (err) {
    console.error(err)
  } finally {
    profileLoading.value = false
  }
}

const handleSaveProfile = async () => {
  if (!profileFormRef.value) return
  await profileFormRef.value.validate(async (valid) => {
    if (!valid) return
    savingProfile.value = true
    try {
      await updateStudentProfile(profileForm)
      ElMessage.success('档案保存成功')
      userStore.fetchCurrentUser()
    } catch (err) {
      console.error(err)
    } finally {
      savingProfile.value = false
    }
  })
}

const fetchSkills = async () => {
  skillsLoading.value = true
  try {
    const res = await getStudentSkills()
    skills.value = res || []
  } catch (err) {
    console.error(err)
  } finally {
    skillsLoading.value = false
  }
}

const fetchSystemTags = async () => {
  try {
    systemTags.value = await getSkillTags()
  } catch (err) {
    console.error(err)
  }
}

const handleProficiencyChange = async (row, val) => {
  try {
    await updateStudentSkill(row.id, { proficiency: val })
    ElMessage.success(`已更新 ${row.tagName} 熟练度为 ${val} 星`)
  } catch (err) {
    fetchSkills()
  }
}

const handleDeleteSkill = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该技能吗？', '提示', { type: 'warning' })
    await deleteStudentSkill(id)
    ElMessage.success('技能已删除')
    fetchSkills()
  } catch (err) {
    // cancelled
  }
}

const openAddSkillDialog = () => {
  selectedTagId.value = null
  skillForm.skillTagId = null
  skillForm.tagName = ''
  skillForm.direction = profileForm.expectDirection || '后端开发'
  skillForm.proficiency = 3
  skillDialogVisible.value = true
}

const handleSelectExistingTag = (tagId) => {
  if (tagId) {
    const tag = systemTags.value.find(t => t.id === tagId)
    if (tag) {
      skillForm.skillTagId = tag.id
      skillForm.tagName = tag.name
      skillForm.direction = tag.direction
    }
  } else {
    skillForm.skillTagId = null
  }
}

const handleConfirmAddSkill = async () => {
  if (!skillForm.skillTagId && !skillForm.tagName.trim()) {
    ElMessage.warning('请选择已有标签或输入自定义技能名称')
    return
  }
  savingSkill.value = true
  try {
    const payload = {
      proficiency: skillForm.proficiency
    }
    if (skillForm.skillTagId) {
      payload.skillTagId = skillForm.skillTagId
    } else {
      payload.tagName = skillForm.tagName.trim()
      payload.direction = skillForm.direction
    }
    await addStudentSkill(payload)
    ElMessage.success('技能添加成功')
    skillDialogVisible.value = false
    fetchSkills()
  } catch (err) {
    console.error(err)
  } finally {
    savingSkill.value = false
  }
}

onMounted(() => {
  fetchProfile()
  fetchSkills()
  fetchSystemTags()
})
</script>

<style scoped>
.student-profile-container {
  padding: 10px 0;
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
.salary-range {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.direction-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
