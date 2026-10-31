<template>
  <div class="page-container">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">系统用户与账号管理</span>
          <div class="header-filters">
            <el-select v-model="filterRole" placeholder="按角色筛选" clearable style="width: 130px" @change="handleSearch">
              <el-option label="学生" :value="1" />
              <el-option label="企业" :value="2" />
              <el-option label="管理员" :value="3" />
            </el-select>

            <el-select v-model="filterStatus" placeholder="账号状态" clearable style="width: 120px" @change="handleSearch">
              <el-option label="正常" :value="1" />
              <el-option label="禁用" :value="2" />
              <el-option label="待审核" :value="0" />
            </el-select>

            <el-input
              v-model="keyword"
              placeholder="搜索用户名、姓名或手机"
              clearable
              style="width: 220px"
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

      <el-table :data="users" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleTagType(row.role)">{{ row.roleName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="nickname" label="昵称 / 姓名" min-width="120" />
        <el-table-column prop="phone" label="手机号码" width="130">
          <template #default="{ row }">{{ row.phone || '-' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="150">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="账号状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : (row.status === 2 ? 'danger' : 'warning')">
              {{ row.status === 1 ? '正常' : (row.status === 2 ? '禁用' : '待审') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastLoginTime" label="最近登录" width="160">
          <template #default="{ row }">{{ row.lastLoginTime || '-' }}</template>
        </el-table-column>
        <el-table-column label="管理操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 1"
              type="danger"
              link
              size="small"
              :disabled="userStore.userId === row.id"
              @click="toggleUserStatus(row, 2)"
            >
              禁用
            </el-button>
            <el-button
              v-else
              type="success"
              link
              size="small"
              @click="toggleUserStatus(row, 1)"
            >
              启用
            </el-button>

            <el-button
              type="warning"
              link
              size="small"
              @click="handleResetPassword(row)"
            >
              重置密码
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loading" description="没有符合条件的用户" />
        </template>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.current"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminUsers, updateAdminUserStatus, resetAdminUserPassword } from '@/api/admin'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const users = ref([])
const filterRole = ref(null)
const filterStatus = ref(null)
const keyword = ref('')

const pagination = reactive({
  current: 1,
  size: 10,
  total: 0
})

const getRoleTagType = (role) => {
  if (role === 1) return 'primary'
  if (role === 2) return 'success'
  if (role === 3) return 'danger'
  return 'info'
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const params = {
      current: pagination.current,
      size: pagination.size,
      role: filterRole.value || undefined,
      status: filterStatus.value !== null ? filterStatus.value : undefined,
      keyword: keyword.value.trim() || undefined
    }
    const res = await getAdminUsers(params)
    users.value = res.records || []
    pagination.total = res.total || 0
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.current = 1
  fetchUsers()
}

const toggleUserStatus = async (row, targetStatus) => {
  const actionText = targetStatus === 1 ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定要${actionText}用户【${row.username}】吗？`, '提示', { type: 'warning' })
    await updateAdminUserStatus(row.id, targetStatus)
    ElMessage.success(`用户已成功${actionText}`)
    fetchUsers()
  } catch (err) {
    // cancelled
  }
}

const handleResetPassword = async (row) => {
  try {
    await ElMessageBox.confirm(`确定将用户【${row.username}】的密码重置为 123456 吗？`, '重置密码', { type: 'warning' })
    await resetAdminUserPassword(row.id)
    ElMessage.success(`用户【${row.username}】的密码已重置为 123456`)
  } catch (err) {
    // cancelled
  }
}

onMounted(() => {
  fetchUsers()
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
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
