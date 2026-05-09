<template>
  <div class="page-container">
    <el-page-header @back="$router.back()" content="奖项得分配置" />

    <el-card class="mt-20">
      <template #header>
        <span>场次奖项得分设置</span>
      </template>

      <el-table :data="events" v-loading="loading">
        <el-table-column prop="name" label="场次名称" />
        <el-table-column prop="round" label="轮次" width="100" />
        <el-table-column label="当前配置" width="150">
          <template #default="{ row }">
            <el-button type="text" @click="editConfig(row)">
              设置得分
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="设置奖项得分" width="500px">
      <p class="config-hint">设置各名次的得分（默认前8名：9,7,6,5,4,3,2,1）</p>
      <el-form :model="configForm" label-width="80px">
        <el-form-item v-for="i in 8" :key="i" :label="`第 ${i} 名`">
          <el-input-number v-model="configForm[`p${i}`]" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfig" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEvents } from '@/api/events'
import { getAwardConfig, updateAwardConfig } from '@/api/ranking'

const route = useRoute()
const compId = route.params.id as string

const events = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const submitting = ref(false)
const currentEventId = ref('')

const configForm = reactive({
  p1: 9, p2: 7, p3: 6, p4: 5, p5: 4, p6: 3, p7: 2, p8: 1
})

const loadData = async () => {
  loading.value = true
  try {
    events.value = await getEvents(compId)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const editConfig = async (row: any) => {
  currentEventId.value = row.id
  try {
    const config: any = await getAwardConfig(row.id)
    const points = config.points || {}
    Object.keys(configForm).forEach(k => {
      const idx = k.replace('p', '')
      configForm[k] = points[idx] || 0
    })
  } catch (e) {
    Object.keys(configForm).forEach((k, i) => {
      configForm[k] = 9 - i
    })
  }
  showDialog.value = true
}

const saveConfig = async () => {
  submitting.value = true
  try {
    const points: Record<string, number> = {}
    Object.keys(configForm).forEach(k => {
      const idx = k.replace('p', '')
      points[idx] = configForm[k]
    })
    await updateAwardConfig(currentEventId.value, points)
    ElMessage.success('保存成功')
    showDialog.value = false
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.config-hint {
  margin-bottom: 20px;
  color: #666;
}
</style>
