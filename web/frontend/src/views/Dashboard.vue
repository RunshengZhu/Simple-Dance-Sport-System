<template>
  <div class="page-container">
    <div class="page-header">
      <h2>赛事概览</h2>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.competitions }}</div>
            <div class="stat-label">赛事数量</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.activeEvents }}</div>
            <div class="stat-label">进行中场次</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.completedEvents }}</div>
            <div class="stat-label">已完成场次</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.competitors }}</div>
            <div class="stat-label">参赛选手</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="12">
        <el-card>
          <template #header>
            <span>最近赛事</span>
          </template>
          <el-empty v-if="!competitions.length" description="暂无赛事" />
          <el-list v-else>
            <el-list-item v-for="comp in competitions" :key="comp.id">
              <el-link type="primary" @click="$router.push(`/competitions/${comp.id}`)">
                {{ comp.name }}
              </el-link>
              <span class="comp-date">{{ comp.date }}</span>
              <el-tag :type="getStatusType(comp.status)">{{ comp.status }}</el-tag>
            </el-list-item>
          </el-list>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card>
          <template #header>
            <span>快捷操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/competitions')">
              创建赛事
            </el-button>
            <el-button type="success" @click="$router.push('/competitions')">
              管理赛事
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCompetitions } from '@/api/competitions'

const stats = ref({
  competitions: 0,
  activeEvents: 0,
  completedEvents: 0,
  competitors: 0
})

const competitions = ref<any[]>([])

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    draft: 'info',
    active: 'success',
    completed: 'warning'
  }
  return map[status] || 'info'
}

const loadData = async () => {
  try {
    const res: any = await getCompetitions({ limit: 5 })
    competitions.value = res.items || []
    stats.value.competitions = res.total || 0
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  margin-bottom: 20px;

  .stat-content {
    text-align: center;
    padding: 20px 0;

    .stat-value {
      font-size: 32px;
      font-weight: bold;
      color: var(--primary-color);
    }

    .stat-label {
      margin-top: 8px;
      color: #666;
      font-size: 14px;
    }
  }
}

.comp-date {
  margin-left: 10px;
  color: #999;
  font-size: 12px;
}

.quick-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;

  .el-button {
    flex: 1;
    min-width: 120px;
  }
}

@media (max-width: 768px) {
  .stat-card {
    .stat-content {
      padding: 16px 0;

      .stat-value {
        font-size: 28px;
      }
    }
  }

  .el-list-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .comp-date {
    margin-left: 0;
  }

  .quick-actions {
    .el-button {
      width: 100%;
      flex: none;
    }
  }
}
</style>
