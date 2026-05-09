<template>
  <div class="page-container">
    <div class="page-header">
      <h2>赛事管理</h2>
      <el-button type="primary" @click="showDialog = true">创建赛事</el-button>
    </div>

    <el-card>
      <el-table :data="list" v-loading="loading">
        <el-table-column prop="name" label="赛事名称" />
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="location" label="地点" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click="$router.push(`/competitions/${row.id}`)">
              详情
            </el-button>
            <el-button type="danger" text size="small" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="创建赛事" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="赛事名称" required>
          <el-input v-model="form.name" placeholder="请输入赛事名称" />
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="请输入地点" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getCompetitions, createCompetition, deleteCompetition } from '@/api/competitions'

const loading = ref(false)
const showDialog = ref(false)
const submitting = ref(false)
const list = ref<any[]>([])

const form = reactive({
  name: '',
  date: '',
  location: ''
})

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    draft: 'info',
    active: 'success',
    completed: 'warning'
  }
  return map[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const res: any = await getCompetitions()
    list.value = res.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!form.name || !form.date) {
    ElMessage.warning('请填写必填项')
    return
  }
  submitting.value = true
  try {
    await createCompetition(form)
    ElMessage.success('创建成功')
    showDialog.value = false
    loadData()
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: string) => {
  await ElMessageBox.confirm('确定要删除该赛事吗？', '提示', { type: 'warning' })
  try {
    await deleteCompetition(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>
