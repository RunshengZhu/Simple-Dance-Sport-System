<template>
  <div class="display-container">
    <div class="display-header">
      <h1>{{ displayTitle }}</h1>
      <div class="live-indicator">
        <span class="dot"></span>
        LIVE
      </div>
    </div>

    <div class="display-content">
      <template v-if="type === 'ranking'">
        <div class="ranking-list">
          <div
            v-for="(item, index) in ranking"
            :key="item.unit"
            :class="['ranking-item', `rank-${index + 1}`]"
          >
            <div class="rank-badge">{{ index + 1 }}</div>
            <div class="unit-name">{{ item.unit }}</div>
            <div class="unit-points">{{ item.total_points.toFixed(1) }}</div>
          </div>
        </div>
      </template>

      <template v-else-if="type === 'results'">
        <div class="results-content">
          <h2>{{ currentEvent?.name }}</h2>
          <el-table :data="results" stripe>
            <el-table-column prop="rank" label="名次" width="100" align="center">
              <template #default="{ row }">
                <span class="result-rank">{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="competitor_number" label="番号" width="120" align="center" />
            <el-table-column prop="competitor_name" label="姓名" />
            <el-table-column prop="unit" label="单位" />
          </el-table>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRanking } from '@/api/ranking'

const route = useRoute()
const type = computed(() => route.params.type as string)

const displayTitle = computed(() => {
  if (type.value === 'ranking') return '单位总分排名'
  if (type.value === 'results') return '比赛成绩'
  return '大屏展示'
})

const ranking = ref<any[]>([])
const results = ref<any[]>([])
const currentEvent = ref<any>(null)
let refreshInterval: number | null = null

const loadRanking = async () => {
  try {
    const res: any = await getRanking('current')
    ranking.value = res.items || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadRanking()
  refreshInterval = window.setInterval(loadRanking, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style lang="scss" scoped>
.display-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  padding: 40px;
}

.display-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 40px;

  h1 {
    font-size: 48px;
    margin: 0;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
  }
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 24px;
  font-weight: bold;
  color: #ff4444;

  .dot {
    width: 16px;
    height: 16px;
    background: #ff4444;
    border-radius: 50%;
    animation: pulse 1s infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.ranking-list {
  .ranking-item {
    display: flex;
    align-items: center;
    padding: 20px 30px;
    margin-bottom: 15px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    transition: all 0.3s;

    &:hover {
      background: rgba(255, 255, 255, 0.15);
      transform: scale(1.02);
    }

    &.rank-1 {
      background: linear-gradient(90deg, #ffd700 0%, #ff8c00 100%);
      color: #1a1a2e;
    }

    &.rank-2 {
      background: linear-gradient(90deg, #c0c0c0 0%, #a0a0a0 100%);
      color: #1a1a2e;
    }

    &.rank-3 {
      background: linear-gradient(90deg, #cd7f32 0%, #a0522d 100%);
    }

    .rank-badge {
      font-size: 36px;
      font-weight: bold;
      width: 80px;
    }

    .unit-name {
      font-size: 32px;
      flex: 1;
    }

    .unit-points {
      font-size: 48px;
      font-weight: bold;
    }
  }
}

.results-content {
  h2 {
    font-size: 36px;
    text-align: center;
    margin-bottom: 30px;
  }

  :deep(.el-table) {
    background: transparent;
    color: white;

    .el-table__header-wrapper th {
      background: rgba(255, 255, 255, 0.1);
      color: white;
      font-size: 18px;
    }

    .el-table__body-wrapper tr {
      background: rgba(255, 255, 255, 0.05);
    }

    .result-rank {
      font-size: 24px;
      font-weight: bold;
    }
  }
}

@media (max-width: 768px) {
  .display-container {
    padding: 20px;
  }

  .display-header h1 {
    font-size: 28px;
  }

  .ranking-item {
    padding: 15px 20px !important;

    .rank-badge {
      font-size: 24px !important;
      width: 50px !important;
    }

    .unit-name {
      font-size: 20px !important;
    }

    .unit-points {
      font-size: 32px !important;
    }
  }
}
</style>
