<template>
  <div class="page-container">
    <el-page-header @back="$router.back()" content="赛事详情" />

    <el-card class="mt-20" v-if="competition">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="赛事名称">{{ competition.name }}</el-descriptions-item>
        <el-descriptions-item label="日期">{{ competition.date }}</el-descriptions-item>
        <el-descriptions-item label="地点">{{ competition.location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(competition.status)">{{ competition.status }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="flex-between">
              <span>场次列表</span>
              <el-button type="primary" size="small" @click="$router.push(`/competitions/${id}/events`)">
                管理场次
              </el-button>
            </div>
          </template>
          <el-table :data="events" v-loading="loading">
            <el-table-column prop="name" label="场次名称" />
            <el-table-column prop="round" label="轮次" width="100" />
            <el-table-column prop="scoring_type" label="评分类型" width="100" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getEventStatusType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'pending'"
                  type="primary"
                  text
                  size="small"
                  @click="$router.push(`/competitions/${id}/scoring/${row.id}`)"
                >
                  开始评分
                </el-button>
                <el-button type="text" size="small" @click="viewResults(row.id)">
                  查看成绩
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <span>快捷操作</span>
          </template>
          <div class="action-buttons">
            <el-button type="primary" @click="$router.push(`/competitions/${id}/competitors`)">
              选手管理
            </el-button>
            <el-button type="success" @click="$router.push(`/competitions/${id}/events`)">
              场次管理
            </el-button>
            <el-button type="warning" @click="$router.push(`/competitions/${id}/ranking`)">
              单位总分
            </el-button>
            <el-button type="info" @click="$router.push(`/competitions/${id}/awards`)">
              奖项配置
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCompetition } from '@/api/competitions'
import { getEvents } from '@/api/events'

const route = useRoute()
const id = route.params.id as string

const competition = ref<any>(null)
const events = ref<any[]>([])
const loading = ref(false)

const getStatusType = (status: string) => {
  const map: Record<string, string> = { draft: 'info', active: 'success', completed: 'warning' }
  return map[status] || 'info'
}

const getEventStatusType = (status: string) => {
  const map: Record<string, string> = { pending: 'info', scoring: 'success', completed: 'success' }
  return map[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    competition.value = await getCompetition(id)
    events.value = await getEvents(id)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const viewResults = (eventId: string) => {
  ElMessage.info('成绩查看功能开发中')
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
