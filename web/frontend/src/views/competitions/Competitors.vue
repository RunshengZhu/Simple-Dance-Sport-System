<template>
  <div class="page-container">
    <el-page-header @back="$router.back()" content="选手管理" />

    <div class="page-header mt-20">
      <h3>{{ competitionName }} - 选手列表 ({{ list.length }}人)</h3>
      <div class="header-actions">
        <el-button type="success" @click="handleImportTestData" :loading="importing">
          导入测试数据
        </el-button>
        <el-button type="primary" @click="showDialog = true">添加选手</el-button>
      </div>
    </div>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="flex-between">
              <span>导入选手 (CSV)</span>
              <el-upload
                :action="`/api/v1/competitions/${compId}/import-competitors`"
                :headers="{ Authorization: `Bearer ${token}` }"
                :show-file-list="false"
                :on-success="handleUploadSuccess"
                :on-error="handleUploadError"
                accept=".csv"
              >
                <el-button type="primary" size="small">上传CSV文件</el-button>
              </el-upload>
            </div>
          </template>
          <el-alert type="info" :closable="false">
            CSV格式要求: 背番号,姓名,学校/单位,参赛组别
          </el-alert>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt-20">
      <el-table :data="list" v-loading="loading">
        <el-table-column prop="number" label="番号" width="80" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="unit" label="单位" />
        <el-table-column prop="group_name" label="组别" />
        <el-table-column prop="is_couple" label="双人" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_couple" type="warning" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="danger" text size="small" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="添加选手" width="600px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="番号" required>
          <el-input v-model="form.number" placeholder="请输入番号" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="单位" required>
          <el-input v-model="form.unit" placeholder="请输入单位" />
        </el-form-item>
        <el-form-item label="组别">
          <el-input v-model="form.group_name" placeholder="请输入组别" />
        </el-form-item>
        <el-form-item label="双人项目">
          <el-switch v-model="form.is_couple" />
        </el-form-item>
        <template v-if="form.is_couple">
          <el-form-item label="搭档番号">
            <el-input v-model="form.partner_number" placeholder="搭档的番号" />
          </el-form-item>
          <el-form-item label="搭档单位">
            <el-input v-model="form.partner_unit" placeholder="搭档的单位" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="submitting">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCompetition } from '@/api/competitions'
import { getCompetitors, createCompetitor, deleteCompetitor } from '@/api/competitors'
import request from '@/api/request'

const route = useRoute()
const compId = route.params.id as string

const token = computed(() => localStorage.getItem('token') || '')

const competitionName = ref('')
const list = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const submitting = ref(false)
const importing = ref(false)

const form = reactive({
  number: '',
  name: '',
  unit: '',
  group_name: '',
  is_couple: false,
  partner_number: '',
  partner_unit: ''
})

const loadData = async () => {
  loading.value = true
  try {
    const comp: any = await getCompetition(compId)
    competitionName.value = comp.name
    list.value = await getCompetitors(compId)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!form.number || !form.name || !form.unit) {
    ElMessage.warning('请填写必填项')
    return
  }
  submitting.value = true
  try {
    await createCompetitor(compId, form)
    ElMessage.success('添加成功')
    showDialog.value = false
    Object.keys(form).forEach(k => (form as any)[k] = '')
    form.is_couple = false
    loadData()
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (id: string) => {
  try {
    await deleteCompetitor(compId, id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    console.error(e)
  }
}

const handleImportTestData = async () => {
  importing.value = true
  try {
    const res: any = await request.post(`/api/v1/competitions/${compId}/setup-from-test-data`)
    ElMessage.success(`导入完成: ${res.competitors_imported}选手, ${res.events_imported}场次`)
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

const handleUploadSuccess = (res: any) => {
  ElMessage.success(`导入成功: ${res.imported}选手`)
  loadData()
}

const handleUploadError = () => {
  ElMessage.error('导入失败')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.header-actions {
  display: flex;
  gap: 10px;
}
</style>
