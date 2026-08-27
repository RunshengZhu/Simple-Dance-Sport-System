<template>
  <div class="public-viewer-container">
    <div class="header">
      <div class="logo">🏆 体育舞蹈评分系统</div>
    </div>

    <div class="search-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索赛事名称..."
        @input="handleSearch"
        clearable
        size="large"
      >
        <template #prefix>
          <span>🔍</span>
        </template>
      </el-input>
    </div>

    <div class="competition-list" v-if="!selectedCompetition">
      <div class="section-title">
        <span>进行中的赛事</span>
      </div>

      <div
        v-for="comp in competitions"
        :key="comp.id"
        class="competition-card"
        @click="selectCompetition(comp)"
      >
        <div class="comp-header">
          <div class="comp-name">{{ comp.name }}</div>
          <div class="comp-status" :class="comp.status">
            {{ statusText[comp.status] }}
          </div>
        </div>
        <div class="comp-meta">
          <div class="meta-item">
            <span class="icon">📅</span>
            {{ comp.date }}
          </div>
          <div class="meta-item">
            <span class="icon">📍</span>
            {{ comp.location }}
          </div>
        </div>
      </div>

      <div class="empty-state" v-if="competitions.length === 0">
        <div class="icon">🏆</div>
        <div class="text">暂无进行中的赛事</div>
      </div>
    </div>

    <div class="competition-detail" v-else>
      <div class="back-nav" @click="goBack">
        <span class="icon">←</span>
        <span>返回赛事列表</span>
      </div>

      <div class="detail-header">
        <div class="comp-name">{{ selectedCompetition.name }}</div>
        <div class="comp-meta">
          <span>{{ selectedCompetition.date }}</span>
          <span>{{ selectedCompetition.location }}</span>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="mobile-tabs">
        <el-tab-pane label="场次" name="events">
          <div class="event-list">
            <div
              v-for="event in events"
              :key="event.id"
              class="event-card"
              @click="selectEvent(event)"
            >
              <div class="event-info">
                <div class="event-name">{{ event.name }}</div>
                <div class="event-meta">
                  <span class="tag">{{ event.scoring_type === 'mark' ? 'Mark制' : '顺位制' }}</span>
                  <span class="tag">第{{ event.round }}轮</span>
                </div>
              </div>
              <div class="event-status" :class="event.status">
                {{ eventStatusText[event.status] }}
              </div>
            </div>

            <div class="empty-state" v-if="events.length === 0">
              <div class="icon">📋</div>
              <div class="text">暂无场次</div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="排名" name="ranking">
          <div class="ranking-list">
            <div
              v-for="(item, index) in ranking"
              :key="index"
              class="ranking-card"
            >
              <div class="rank" :class="`rank-${index + 1}`">
                {{ index + 1 }}
              </div>
              <div class="info">
                <div class="unit-name">{{ item.unit }}</div>
                <div class="total-points">{{ item.total_points }} 分</div>
              </div>
            </div>

            <div class="empty-state" v-if="ranking.length === 0">
              <div class="icon">🏅</div>
              <div class="text">暂无排名数据</div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div class="event-result-dialog" v-if="selectedEvent">
      <div class="dialog-overlay" @click="closeEventResult"></div>
      <div class="dialog-content">
        <div class="dialog-header">
          <div class="title">{{ selectedEvent.name }}</div>
          <div class="close-btn" @click="closeEventResult">×</div>
        </div>

        <div class="dialog-body">
          <div class="result-list">
            <div
              v-for="(result, index) in eventResults"
              :key="index"
              class="result-item"
            >
              <div class="rank" :class="`rank-${result.rank}`">
                {{ result.rank }}
              </div>
              <div class="competitor-info">
                <div class="number">{{ result.competitor_number }}</div>
                <div class="name">{{ result.competitor_name }}</div>
              </div>
              <div class="unit">{{ result.unit }}</div>
            </div>

            <div class="empty-state" v-if="eventResults.length === 0">
              <div class="icon">🏆</div>
              <div class="text">暂无比赛结果</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const searchKeyword = ref('')
const competitions = ref<any[]>([])
const selectedCompetition = ref<any>(null)
const activeTab = ref('events')
const events = ref<any[]>([])
const ranking = ref<any[]>([])
const selectedEvent = ref<any>(null)
const eventResults = ref<any[]>([])

const statusText: Record<string, string> = {
  active: '进行中',
  completed: '已结束',
  pending: '未开始'
}

const eventStatusText: Record<string, string> = {
  pending: '待评分',
  in_progress: '评分中',
  completed: '已完成'
}

const handleSearch = async () => {
  try {
    const params: any = {}
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    const res: any = await request.get('/competitions/', { params })
    competitions.value = res.items || []
  } catch (error) {
    console.error('搜索失败:', error)
  }
}

const selectCompetition = async (comp: any) => {
  selectedCompetition.value = comp
  await loadCompetitionData()
}

const loadCompetitionData = async () => {
  if (!selectedCompetition.value) return

  try {
    const [eventsRes, rankingRes] = await Promise.all([
      request.get(`/competitions/${selectedCompetition.value.id}/events`),
      request.get(`/competitions/${selectedCompetition.value.id}/ranking`)
    ])

    events.value = eventsRes || []
    ranking.value = rankingRes?.items || []
  } catch (error) {
    console.error('加载数据失败:', error)
  }
}

const selectEvent = async (event: any) => {
  selectedEvent.value = event

  if (event.status === 'completed') {
    try {
      const res = await request.get(`/events/${event.id}/results`)
      eventResults.value = res || []
    } catch (error) {
      eventResults.value = []
    }
  }
}

const closeEventResult = () => {
  selectedEvent.value = null
  eventResults.value = []
}

const goBack = () => {
  selectedCompetition.value = null
  events.value = []
  ranking.value = []
}

onMounted(() => {
  handleSearch()
})
</script>

<style scoped lang="scss">
.public-viewer-container {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 20px;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 24px 16px;
  text-align: center;

  .logo {
    font-size: 20px;
    font-weight: 600;
  }
}

.search-bar {
  padding: 16px;
  background: #fff;
  margin-bottom: 16px;

  :deep(.el-input__wrapper) {
    border-radius: 24px;
    padding: 4px 16px;
  }
}

.competition-list {
  padding: 0 16px;

  .section-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #333;
  }
}

.competition-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s;

  &:active {
    transform: scale(0.98);
  }

  .comp-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;

    .comp-name {
      font-size: 18px;
      font-weight: 600;
      color: #333;
      flex: 1;
    }

    .comp-status {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;

      &.active {
        background: #e6f7ff;
        color: #1890ff;
      }

      &.completed {
        background: #f6ffed;
        color: #52c41a;
      }

      &.pending {
        background: #fff7e6;
        color: #faad14;
      }
    }
  }

  .comp-meta {
    display: flex;
    gap: 16px;
    font-size: 14px;
    color: #999;

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;

      .icon {
        font-size: 16px;
      }
    }
  }
}

.competition-detail {
  .back-nav {
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #409eff;
    cursor: pointer;
    background: #fff;
    margin-bottom: 16px;

    .icon {
      font-size: 20px;
    }
  }

  .detail-header {
    padding: 0 16px 16px;
    background: #fff;
    margin-bottom: 16px;

    .comp-name {
      font-size: 24px;
      font-weight: 700;
      margin-bottom: 8px;
    }

    .comp-meta {
      display: flex;
      gap: 16px;
      font-size: 14px;
      color: #999;
    }
  }
}

.mobile-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 0;
    background: #fff;
    padding: 0 16px;
  }

  :deep(.el-tabs__nav-wrap::after) {
    height: 1px;
  }

  :deep(.el-tabs__item) {
    font-size: 16px;
    height: 48px;
    line-height: 48px;
  }
}

.event-list, .ranking-list {
  padding: 16px;
}

.event-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s;

  &:active {
    transform: scale(0.98);
  }

  .event-info {
    flex: 1;

    .event-name {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .event-meta {
      display: flex;
      gap: 8px;

      .tag {
        padding: 2px 8px;
        background: #f0f0f0;
        border-radius: 4px;
        font-size: 12px;
        color: #666;
      }
    }
  }

  .event-status {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;

    &.completed {
      background: #f6ffed;
      color: #52c41a;
    }

    &.in_progress {
      background: #e6f7ff;
      color: #1890ff;
    }

    &.pending {
      background: #fff7e6;
      color: #faad14;
    }
  }
}

.ranking-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  .rank {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    background: #f0f0f0;
    color: #666;

    &.rank-1 {
      background: linear-gradient(135deg, #ffd700, #ffb347);
      color: #fff;
    }

    &.rank-2 {
      background: linear-gradient(135deg, #c0c0c0, #a0a0a0);
      color: #fff;
    }

    &.rank-3 {
      background: linear-gradient(135deg, #cd7f32, #b8860b);
      color: #fff;
    }
  }

  .info {
    flex: 1;

    .unit-name {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 4px;
    }

    .total-points {
      font-size: 14px;
      color: #409eff;
    }
  }
}

.empty-state {
  text-align: center;
  padding: 40px 20px;

  .icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  .text {
    font-size: 16px;
    color: #999;
  }
}

.event-result-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-end;

  .dialog-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
  }

  .dialog-content {
    position: relative;
    width: 100%;
    max-height: 80vh;
    background: #fff;
    border-radius: 16px 16px 0 0;
    overflow: hidden;
    animation: slideUp 0.3s ease;
  }

  .dialog-header {
    padding: 16px;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 18px;
      font-weight: 600;
    }

    .close-btn {
      font-size: 32px;
      color: #999;
      cursor: pointer;
      line-height: 1;
    }
  }

  .dialog-body {
    max-height: calc(80vh - 60px);
    overflow-y: auto;
    padding: 16px;
  }
}

@keyframes slideUp {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

.result-list {
  .result-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 8px;
    margin-bottom: 8px;

    .rank {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      font-weight: 700;
      background: #e0e0e0;
      color: #666;

      &.rank-1 {
        background: #ffd700;
        color: #fff;
      }

      &.rank-2 {
        background: #c0c0c0;
        color: #fff;
      }

      &.rank-3 {
        background: #cd7f32;
        color: #fff;
      }
    }

    .competitor-info {
      flex: 1;

      .number {
        font-size: 14px;
        color: #409eff;
        margin-bottom: 2px;
      }

      .name {
        font-size: 16px;
        font-weight: 600;
      }
    }

    .unit {
      font-size: 14px;
      color: #999;
    }
  }
}

@media (min-width: 769px) {
  .public-viewer-container {
    max-width: 600px;
    margin: 0 auto;
  }
}
</style>
