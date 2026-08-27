<template>
  <div class="judge-scoring-container">
    <div class="mobile-header">
      <div class="back-button" @click="goBack">←</div>
      <div class="title">裁判评分</div>
      <div class="action" @click="submitScores" :class="{ disabled: !hasChanges }">
        提交
      </div>
    </div>

    <div class="competition-info" v-if="event">
      <div class="event-name">{{ event.name }}</div>
      <div class="event-meta">
        <span class="scoring-type">{{ scoringTypeText }}</span>
        <span class="round">第 {{ event.round }} 轮</span>
      </div>
    </div>

    <div class="judge-selector" v-if="event">
      <div class="label">选择裁判</div>
      <div class="judge-list">
        <div
          v-for="judge in judges"
          :key="judge.id"
          class="judge-item"
          :class="{ active: selectedJudge === judge.id }"
          @click="selectJudge(judge.id)"
        >
          {{ judge.name }}
        </div>
      </div>
    </div>

    <div class="competitor-grid" v-if="competitors.length > 0">
      <div class="grid-title">
        <span>参赛选手</span>
        <span class="count">{{ competitors.length }} 人</span>
      </div>
      <div class="scoring-grid">
        <div
          v-for="comp in competitors"
          :key="comp.number"
          class="scoring-item"
          :class="{ selected: isSelected(comp.number) }"
          @click="toggleSelection(comp.number)"
        >
          <div class="number">{{ comp.number }}</div>
        </div>
      </div>
    </div>

    <div class="empty-state" v-else>
      <div class="icon">📋</div>
      <div class="text">暂无参赛选手</div>
    </div>

    <div class="action-bar">
      <div class="action-btn secondary" @click="clearAll">清空选择</div>
      <div class="action-btn primary" @click="submitScores" :class="{ disabled: !hasChanges }">
        提交评分
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEventDetails, getCompetitors, getScores, submitScores as submitScoresAPI } from '@/api/judge'

const router = useRouter()
const route = useRoute()

const event = ref<any>(null)
const competitors = ref<any[]>([])
const selectedJudge = ref('judge1')
const selectedCompetitors = ref<Set<string>>(new Set())
const originalSelection = ref<Set<string>>(new Set())
const loading = ref(false)

const judges = [
  { id: 'judge1', name: '裁判1号' },
  { id: 'judge2', name: '裁判2号' },
  { id: 'judge3', name: '裁判3号' },
  { id: 'judge4', name: '裁判4号' },
  { id: 'judge5', name: '裁判5号' }
]

const scoringTypeText = computed(() => {
  if (!event.value) return ''
  return event.value.scoring_type === 'mark' ? 'Mark制' : '顺位制'
})

const hasChanges = computed(() => {
  if (selectedCompetitors.value.size === 0 && originalSelection.value.size === 0) {
    return false
  }
  if (selectedCompetitors.value.size !== originalSelection.value.size) {
    return true
  }
  for (const num of selectedCompetitors.value) {
    if (!originalSelection.value.has(num)) {
      return true
    }
  }
  return false
})

const isSelected = (number: string) => {
  return selectedCompetitors.value.has(number)
}

const toggleSelection = (number: string) => {
  if (selectedCompetitors.value.has(number)) {
    selectedCompetitors.value.delete(number)
  } else {
    selectedCompetitors.value.add(number)
  }
  selectedCompetitors.value = new Set(selectedCompetitors.value)
}

const selectJudge = (judgeId: string) => {
  selectedJudge.value = judgeId
  loadScores()
}

const loadScores = async () => {
  if (!event.value) return

  try {
    const scores = await getScores(event.value.id, selectedJudge.value)
    selectedCompetitors.value = new Set(
      scores.filter((s: any) => s.mark).map((s: any) => s.competitor_number)
    )
    originalSelection.value = new Set(selectedCompetitors.value)
  } catch (error) {
    console.error('加载评分失败:', error)
  }
}

const clearAll = () => {
  selectedCompetitors.value = new Set()
}

const submitScores = async () => {
  if (!event.value || !hasChanges.value) return

  try {
    loading.value = true
    const records = Array.from(selectedCompetitors.value).map((number) => ({
      event_id: event.value.id,
      judge_id: selectedJudge.value,
      competitor_number: number,
      mark: true,
      placement: 0,
      score: 0
    }))

    await submitScoresAPI(event.value.id, records)

    ElMessage.success('评分提交成功')
    originalSelection.value = new Set(selectedCompetitors.value)
  } catch (error) {
    ElMessage.error('提交失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.back()
}

const loadData = async () => {
  const eventId = route.params.eventId as string
  const competitionId = route.params.id as string

  try {
    event.value = await getEventDetails(eventId)
    competitors.value = await getCompetitors(competitionId, event.value.competitor_numbers)
    await loadScores()
  } catch (error) {
    ElMessage.error('加载数据失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.judge-scoring-container {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 100px;
}

.mobile-header {
  position: sticky;
  top: 0;
  background: #fff;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  z-index: 100;

  .back-button {
    font-size: 24px;
    padding: 8px;
    cursor: pointer;
  }

  .title {
    flex: 1;
    text-align: center;
    font-size: 18px;
    font-weight: 600;
  }

  .action {
    font-size: 16px;
    color: #409eff;
    cursor: pointer;

    &.disabled {
      color: #ccc;
    }
  }
}

.competition-info {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 20px 16px;
  margin-bottom: 16px;

  .event-name {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 8px;
  }

  .event-meta {
    display: flex;
    gap: 12px;
    font-size: 14px;
    opacity: 0.9;
  }
}

.judge-selector {
  background: #fff;
  padding: 16px;
  margin-bottom: 16px;
  border-radius: 8px;

  .label {
    font-size: 14px;
    color: #999;
    margin-bottom: 12px;
  }

  .judge-list {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .judge-item {
    padding: 8px 16px;
    border: 1px solid #dcdfe6;
    border-radius: 20px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.3s;

    &.active {
      background: #409eff;
      color: #fff;
      border-color: #409eff;
    }
  }
}

.competitor-grid {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;

  .grid-title {
    padding: 16px;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;

    .count {
      font-size: 14px;
      color: #999;
      font-weight: normal;
    }
  }

  .scoring-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 12px;
    padding: 16px;
  }

  .scoring-item {
    aspect-ratio: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: #f5f7fa;
    border: 2px solid #e4e7ed;
    border-radius: 12px;
    transition: all 0.3s;
    cursor: pointer;

    &:active {
      transform: scale(0.95);
    }

    &.selected {
      background: linear-gradient(135deg, #409eff, #66b1ff);
      border-color: #409eff;
      color: #fff;
      transform: scale(1.05);
      box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
    }

    .number {
      font-size: 32px;
      font-weight: 700;
      color: #333;
    }

    &.selected .number {
      color: #fff;
    }
  }
}

.empty-state {
  text-align: center;
  padding: 60px 20px;

  .icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  .text {
    font-size: 16px;
    color: #999;
  }
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 16px;
  display: flex;
  gap: 12px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);

  .action-btn {
    flex: 1;
    height: 48px;
    border-radius: 24px;
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s;

    &.secondary {
      background: #f5f7fa;
      color: #666;
      border: 1px solid #dcdfe6;
    }

    &.primary {
      background: #409eff;
      color: #fff;

      &.disabled {
        background: #a0cfff;
        cursor: not-allowed;
      }
    }

    &:active:not(.disabled) {
      transform: scale(0.98);
    }
  }
}

@media (min-width: 769px) {
  .judge-scoring-container {
    max-width: 800px;
    margin: 0 auto;
  }

  .scoring-grid {
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)) !important;
  }
}
</style>
