<template>
  <div class="page-container">
    <el-page-header @back="$router.back()" content="单位总分排名" />

    <el-card class="mt-20">
      <template #header>
        <div class="flex-between">
          <span>实时排名</span>
          <el-button type="primary" text @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-table :data="ranking" v-loading="loading" stripe>
        <el-table-column prop="rank" label="排名" width="80" align="center">
          <template #default="{ $index }">
            <el-tag :type="getRankType($index + 1)" size="large">
              {{ $index + 1 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="参赛单位" />
        <el-table-column prop="total_points" label="总分" width="120" align="center">
          <template #default="{ row }">
            <span class="total-points">{{ row.total_points.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="得分项目数" width="120" align="center" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click="showDetails(row)">
              明细
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDetailDialog" title="得分明细" width="800px">
      <el-table :data="detailRecords">
        <el-table-column prop="event_name" label="场次" />
        <el-table-column prop="competitor_number" label="番号" width="80" />
        <el-table-column prop="competitor_name" label="选手" />
        <el-table-column prop="rank" label="名次" width="80" align="center" />
        <el-table-column prop="points" label="得分" width="80" align="center" />
        <el-table-column label="分摊" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_split" type="warning" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { getRanking } from '@/api/ranking'

const route = useRoute()
const compId = route.params.id as string

const ranking = ref<any[]>([])
const loading = ref(false)
const showDetailDialog = ref(false)
const detailRecords = ref<any[]>([])

const getRankType = (rank: number) => {
  if (rank === 1) return 'warning'
  if (rank === 2) return 'info'
  if (rank === 3) return ''
  return 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const res: any = await getRanking(compId)
    ranking.value = res.items || []
    ranking.value.forEach((item: any, index: number) => {
      item.rank = index + 1
    })
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const showDetails = (row: any) => {
  detailRecords.value = row.records || []
  showDetailDialog.value = true
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.total-points {
  font-size: 20px;
  font-weight: bold;
  color: var(--primary-color);
}
</style>
