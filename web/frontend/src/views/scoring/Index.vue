<template>
  <div class="scoring-container">
    <el-card class="scoring-header">
      <div class="header-content">
        <div class="event-info">
          <h2>{{ event?.name }}</h2>
          <el-tag :type="getStatusType(event?.status)" size="large">
            {{ event?.scoring_type === 'mark' ? 'Mark制淘汰赛' : '顺位法排名赛' }}
          </el-tag>
          <el-tag v-if="event?.dances && event?.dances.length" size="large">
            舞种: {{ Array.isArray(event.dances) ? event.dances.join(',') : event.dances }}
          </el-tag>
          <el-tag type="info" size="large">
            轮次: {{ event?.round }}
          </el-tag>
          <el-tag type="warning" size="large">
            晋级: {{ event?.advancement_count }}人
          </el-tag>
        </div>
        <div class="judge-info">
          <span>当前裁判: </span>
          <el-select v-model="currentJudgeId" placeholder="选择裁判" style="width: 150px">
            <el-option v-for="j in judges" :key="j.id" :label="j.name" :value="j.id" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-card class="scoring-content">
      <template v-if="event?.scoring_type === 'mark'">
        <div class="mark-header">
          <h3>Mark制评分 - 点击选择晋级的选手</h3>
          <div class="mark-stats">
            <span>已选: {{ selectedNumbers.size }} / {{ event?.advancement_count }} (晋级人数)</span>
            <el-button type="danger" text size="small" @click="selectedNumbers.clear()">清空选择</el-button>
          </div>
        </div>
        <div class="competitor-grid">
          <el-card
            v-for="comp in eventCompetitors"
            :key="comp.number"
            :class="{ selected: selectedNumbers.has(comp.number) }"
            :class:="{
              'el-over': selectedNumbers.size >= (event?.advancement_count || 0) && !selectedNumbers.has(comp.number)
            }"
            class="competitor-card"
            @click="toggleSelect(comp.number)"
          >
            <div class="competitor-number">{{ comp.number }}</div>
            <div class="competitor-name">{{ comp.name }}</div>
            <div class="competitor-unit">{{ comp.unit }}</div>
          </el-card>
        </div>
        <el-empty v-if="eventCompetitors.length === 0" description="该场次暂无参赛选手，请先在赛程中配置参赛选手" />
      </template>

      <template v-else>
        <h3>顺位法评分 - 输入选手排名顺序</h3>
        <p class="tip">请按排名从第1名到第N名依次选择选手</p>
        <div class="ranking-list">
          <div v-for="(item, index) in rankingList" :key="index" class="ranking-item">
            <span class="rank-number" :class="{ 'top-rank': index < 3 }">
              {{ index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `第${index + 1}名` }}
            </span>
            <el-select v-model="item.number" placeholder="选择选手" filterable style="flex: 1">
              <el-option
                v-for="comp in eventCompetitors"
                :key="comp.number"
                :label="`${comp.number} - ${comp.name} (${comp.unit})`"
                :value="comp.number"
              />
            </el-select>
            <el-button type="danger" text @click="removeRank(index)" v-if="rankingList.length > 1">
              删除
            </el-button>
          </div>
          <el-button type="primary" @click="addRank" class="add-rank-btn">
            + 添加排名
          </el-button>
        </div>
      </template>
    </el-card>

    <el-card class="scoring-footer">
      <div class="footer-actions">
        <el-button @click="$router.back()">返回</el-button>
        <el-button type="warning" @click="handleCalculate" :loading="calculating">
          计算成绩
        </el-button>
        <el-button type="success" size="large" @click="handleSubmit" :loading="submitting">
          提交评分
        </el-button>
      </div>
    </el-card>

    <el-dialog v-model="showResultsDialog" title="场次成绩" width="700px">
      <el-table :data="calculatedResults" stripe>
        <el-table-column prop="competitor_number" label="番号" width="80" />
        <el-table-column prop="competitor_name" label="姓名" />
        <el-table-column prop="unit" label="单位" />
        <el-table-column prop="rank" label="排名" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.rank === 1" type="warning" size="small">🥇 第1名</el-tag>
            <el-tag v-else-if="row.rank === 2" size="small">🥈 第2名</el-tag>
            <el-tag v-else-if="row.rank === 3" size="small">🥉 第3名</el-tag>
            <el-tag v-else type="info" size="small">第{{ row.rank }}名</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEvent } from '@/api/events'
import { getCompetitors } from '@/api/competitors'
import { submitScores, getScores, calculateResults } from '@/api/scoring'

const route = useRoute()
const router = useRouter()
const compId = route.params.id as string
const eventId = route.params.eventId as string

const event = ref<any>(null)
const allCompetitors = ref<any[]>([])
const eventCompetitors = ref<any[]>([])
const judges = ref<any[]>([
  { id: 'judge1', name: '裁判1' },
  { id: 'judge2', name: '裁判2' },
  { id: 'judge3', name: '裁判3' },
  { id: 'judge4', name: '裁判4' },
  { id: 'judge5', name: '裁判5' },
  { id: 'judge6', name: '裁判6' },
  { id: 'judge7', name: '裁判7' }
])
const currentJudgeId = ref('judge1')
const selectedNumbers = ref<Set<string>>(new Set())
const rankingList = ref([{ number: '' }])
const submitting = ref(false)
const calculating = ref(false)
const showResultsDialog = ref(false)
const calculatedResults = ref<any[]>([])

const getStatusType = (status?: string) => {
  const map: Record<string, string> = { pending: 'info', scoring: 'warning', completed: 'success' }
  return map[status || ''] || 'info'
}

const loadEventCompetitors = () => {
  if (!event.value?.competitor_numbers || !allCompetitors.value.length) {
    eventCompetitors.value = allCompetitors.value
    return
  }
  const numbers = event.value.competitor_numbers
  eventCompetitors.value = allCompetitors.value.filter(c => numbers.includes(c.number))
}

const toggleSelect = (number: string) => {
  const maxCount = event.value?.advancement_count || 8
  if (selectedNumbers.value.has(number)) {
    selectedNumbers.value.delete(number)
  } else if (selectedNumbers.value.size < maxCount) {
    selectedNumbers.value.add(number)
  }
}

const addRank = () => {
  rankingList.value.push({ number: '' })
}

const removeRank = (index: number) => {
  rankingList.value.splice(index, 1)
}

const handleSubmit = async () => {
  if (!currentJudgeId.value) {
    ElMessage.warning('请选择裁判')
    return
  }

  let records: any[] = []

  if (event.value?.scoring_type === 'mark') {
    if (selectedNumbers.value.size === 0) {
      ElMessage.warning('请至少选择一个选手')
      return
    }
    records = Array.from(selectedNumbers.value).map(number => ({
      event_id: eventId,
      judge_id: currentJudgeId.value,
      competitor_number: number,
      mark: true
    }))
  } else {
    const validRanks = rankingList.value.filter(r => r.number)
    if (validRanks.length === 0) {
      ElMessage.warning('请至少输入一个排名')
      return
    }
    records = validRanks.map((r, index) => ({
      event_id: eventId,
      judge_id: currentJudgeId.value,
      competitor_number: r.number,
      placement: index + 1
    }))
  }

  submitting.value = true
  try {
    await submitScores(eventId, records)
    ElMessage.success('评分已提交')
  } catch (e) {
    console.error(e)
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

const handleCalculate = async () => {
  calculating.value = true
  try {
    const res: any = await calculateResults(eventId)
    calculatedResults.value = res.results || []
    showResultsDialog.value = true
    if (res.results?.length > 0) {
      ElMessage.success('成绩计算完成')
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('计算失败')
  } finally {
    calculating.value = false
  }
}

const loadData = async () => {
  try {
    event.value = await getEvent(eventId)
    allCompetitors.value = await getCompetitors(compId)
    loadEventCompetitors()
    
    if (event.value.status === 'pending') {
      event.value.status = 'scoring'
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style lang="scss" scoped>
.scoring-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.scoring-header {
  margin-bottom: 20px;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 15px;

    h2 {
      margin: 0 0 10px 0;
    }
  }

  .event-info {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .judge-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.scoring-content {
  min-height: 400px;

  .mark-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    h3 {
      margin: 0;
    }

    .mark-stats {
      display: flex;
      align-items: center;
      gap: 15px;
    }
  }

  .tip {
    color: #909399;
    margin-bottom: 15px;
  }
}

.competitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 12px;
}

.competitor-card {
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
  border: 2px solid transparent;

  &:hover {
    transform: scale(1.03);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &.selected {
    background: linear-gradient(135deg, #409eff, #67c23a);
    color: white;
    border-color: #409eff;

    .competitor-unit {
      color: rgba(255, 255, 255, 0.8);
    }
  }

  &.el-over {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .competitor-number {
    font-size: 28px;
    font-weight: bold;
    color: inherit;
  }

  .competitor-name {
    margin-top: 8px;
    font-size: 14px;
    font-weight: 500;
  }

  .competitor-unit {
    font-size: 12px;
    color: #999;
    margin-top: 5px;
  }
}

.ranking-list {
  .ranking-item {
    display: flex;
    align-items: center;
    gap: 15px;
    margin-bottom: 12px;

    .rank-number {
      width: 60px;
      font-weight: bold;
      text-align: center;

      &.top-rank {
        font-size: 20px;
      }
    }

    .el-select {
      flex: 1;
    }
  }

  .add-rank-btn {
    margin-top: 10px;
  }
}

.scoring-footer {
  margin-top: 20px;

  .footer-actions {
    display: flex;
    justify-content: flex-end;
    gap: 15px;

    .el-button {
      min-width: 100px;
    }
  }
}

@media (max-width: 768px) {
  .competitor-grid {
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
  }

  .competitor-card {
    .competitor-number {
      font-size: 22px;
    }

    .competitor-name {
      font-size: 12px;
    }
  }
}
</style>
