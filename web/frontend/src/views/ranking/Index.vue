<template>
  <div class="page-container">
    <el-page-header @back="$router.back()" content="单位总分排名" />

    <el-card class="mt-20">
      <template #header>
        <div class="flex-between">
          <div class="header-left">
            <span>单位总分排名</span>
            <el-tag v-if="lastUpdated" type="info" size="small">
              最后更新: {{ lastUpdated }}
            </el-tag>
          </div>
          <div class="header-actions">
            <el-button type="warning" @click="handleCalculate" :loading="calculating">
              计算总分
            </el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">
              导出Excel
            </el-button>
            <el-button type="primary" text @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="ranking" v-loading="loading" stripe>
        <el-table-column prop="rank" label="排名" width="80" align="center">
          <template #default="{ $index }">
            <el-tag v-if="$index === 0" type="warning" size="large">🥇 {{ $index + 1 }}</el-tag>
            <el-tag v-else-if="$index === 1" size="large">🥈 {{ $index + 1 }}</el-tag>
            <el-tag v-else-if="$index === 2" size="large">🥉 {{ $index + 1 }}</el-tag>
            <el-tag v-else type="info" size="large">{{ $index + 1 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="参赛单位" min-width="150" />
        <el-table-column prop="total_points" label="总分" width="120" align="center" sortable>
          <template #default="{ row }">
            <span class="total-points">{{ row.total_points.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="得分项目数" width="120" align="center" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click="showDetails(row)">
              明细
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="ranking.length === 0 && !loading" description="暂无排名数据，请先完成比赛评分并点击" />
    </el-card>

    <el-dialog v-model="showDetailDialog" title="得分明细" width="900px">
      <el-table :data="detailRecords" stripe>
        <el-table-column prop="event_name" label="场次" min-width="200" />
        <el-table-column prop="competitor_number" label="番号" width="80" />
        <el-table-column prop="competitor_name" label="选手" />
        <el-table-column prop="rank" label="名次" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.rank === 1" type="warning" size="small">🥇 1</el-tag>
            <el-tag v-else-if="row.rank === 2" size="small">🥈 2</el-tag>
            <el-tag v-else-if="row.rank === 3" size="small">🥉 3</el-tag>
            <el-tag v-else type="info" size="small">{{ row.rank }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="points" label="得分" width="80" align="center">
          <template #default="{ row }">
            <strong>{{ row.points.toFixed(1) }}</strong>
          </template>
        </el-table-column>
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
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getRanking, calculateRanking } from '@/api/ranking'
import request from '@/api/request'

const route = useRoute()
const compId = route.params.id as string

const ranking = ref<any[]>([])
const loading = ref(false)
const calculating = ref(false)
const exporting = ref(false)
const showDetailDialog = ref(false)
const detailRecords = ref<any[]>([])
const lastUpdated = ref('')

const loadData = async () => {
  loading.value = true
  try {
    const res: any = await getRanking(compId)
    ranking.value = res.items || []
    ranking.value.forEach((item: any, index: number) => {
      item.rank = index + 1
    })
    lastUpdated.value = new Date().toLocaleTimeString('zh-CN')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleCalculate = async () => {
  calculating.value = true
  try {
    const res: any = await calculateRanking(compId)
    ElMessage.success(`总分计算完成，共${res.units}个单位`)
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error('计算失败')
  } finally {
    calculating.value = false
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    const res: any = await request.get(`/api/v1/competitions/${compId}/export-ranking`)
    ElMessage.success('导出成功')
    
    const link = document.createElement('a')
    link.href = res.download_url
    link.download = `单位总分排名_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.xlsx`
    link.click()
  } catch (e: any) {
    console.error(e)
    if (e.message?.includes('404')) {
      ElMessage.warning('请先计算总分')
    } else {
      ElMessage.error('导出失败')
    }
  } finally {
    exporting.value = false
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
.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.total-points {
  font-size: 20px;
  font-weight: bold;
  color: #409eff;
}
</style>
