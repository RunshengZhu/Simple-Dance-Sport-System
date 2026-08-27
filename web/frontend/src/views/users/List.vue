<template>
  <div class="users-container">
    <el-card class="users-card">
      <template #header>
        <div class="card-header">
          <h2>用户管理</h2>
        </div>
      </template>
      
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)">
              {{ getRoleName(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getUsers } from '@/api/users'

const users = ref([])
const loading = ref(false)

const fetchUsers = async () => {
  loading.value = true
  try {
    const data = await getUsers()
    users.value = data
  } catch (error: any) {
    ElMessage.error(error.message || '获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const getRoleName = (role: string) => {
  const roles: Record<string, string> = {
    admin: '管理员',
    judge: '裁判',
    viewer: '观众'
  }
  return roles[role] || role
}

const getRoleType = (role: string) => {
  const types: Record<string, string> = {
    admin: 'danger',
    judge: 'warning',
    viewer: 'info'
  }
  return types[role] || 'info'
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchUsers()
})
</script>

<style lang="scss" scoped>
.users-container {
  padding: 20px;
}

.users-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    h2 {
      margin: 0;
      font-size: 18px;
    }
  }
}
</style>
