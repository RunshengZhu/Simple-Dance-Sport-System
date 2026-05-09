<template>
  <div class="scoring-container">
    <el-card class="scoring-header">
      <div class="header-content">
        <div class="event-info">
          <h2>{{ event?.name }}</h2>
          <el-tag :type="getStatusType(event?.status)">{{ event?.status }}</el-tag>
        </div>
        <div class="judge-info">
          <span>裁判: </span>
          <el-select v-model="currentJudgeId" placeholder="选择裁判" style="width: 200px">
            <el-option v-for="j in judges" :key="j.id" :label="j.name" :value="j.id" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-card class="scoring-content">
      <template v-if="event?.scoring_type === 'mark'">
        <h3>Mark制评分 - 勾选晋级选手</h3>
        <div class="competitor-grid">
          <el-card
            v-for="comp in competitors"
            :key="comp.id"
            :class="{ selected: selectedNumbers.has(comp.number) }"
            class="competitor-card"
            @click="toggleSelect(comp.number)"
          >
            <div class="competitor-number">{{ comp.number }}</div>
            <div class="competitor-name">{{ comp.name }}</div>
            <div class="competitor-unit">{{ comp.unit }}</div>
          </el-card>
        </div>
      </template>

      <template v-else>
        <h3>顺位法评分 - 输入选手排名</h3>
        <div class="ranking-list">
          <div v-for="(item, index) in rankingList" :key="index" class="ranking-item">
            <span class="rank-number">第{{ index + 1 }}名</span>
            <el-select v-model="item.number" placeholder="选择选手" filterable>
              <el-option
                v-for="comp in competitors"
                :key="comp.id"
                :label="`${comp.number} - ${comp.name}`"
                :value="comp.number"
              />
            </el-select>
            <el-button type="danger" text @click="removeRank(index)" v-if="rankingList.length > 1">
              删除
            </el-button>
          </div>
          <el-button type="primary" @click="addRank" class="add-rank-btn">
            添加排名
          </el-button>
        </div>
      </template>
    </el-card>

    <el-card class="scoring-footer">
      <div class="footer-actions">
        <el-button @click="$router.back()">返回</el-button>
        <el-button type="success" size="large" @click="handleSubmit" :loading="submitting">
          提交评分
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEvent } from '@/api/events'
import { getCompetitors } from '@/api/competitors'
import { submitScores } from '@/api/scoring'

const route = useRoute()
const compId = route.params.id as string
const eventId = route.params.eventId as string

const event = ref<any>(null)
const competitors = ref<any[]>([])
const judges = ref<any[]>([{ id: 'judge1', name: '裁判1' }])
const currentJudgeId = ref('judge1')
const selectedNumbers = ref<Set<string>>(new Set())
const rankingList = ref([{ number: '' }])
const submitting = ref(false)

const getStatusType = (status?: string) => {
  const map: Record<string, string> = { pending: 'info', scoring: 'success', completed: 'success' }
  return map[status || ''] || 'info'
}

const toggleSelect = (number: string) => {
  if (selectedNumbers.value.has(number)) {
    selectedNumbers.value.delete(number)
  } else {
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
  } finally {
    submitting.value = false
  }
}

const loadData = async () => {
  try {
    event.value = await getEvent(eventId)
    competitors.value = await getCompetitors(compId)
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.scoring-header {
  margin-bottom: 20px;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 15px;

    h2 {
      margin: 0;
    }
  }
}

.scoring-content {
  min-height: 400px;

  h3 {
    margin-bottom: 20px;
  }
}

.competitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 15px;
}

.competitor-card {
  cursor: pointer;
  text-align: center;
  transition: all 0.3s;

  &:hover {
    transform: scale(1.02);
  }

  &.selected {
    background: var(--primary-color);
    color: white;

    .competitor-unit {
      color: rgba(255, 255, 255, 0.8);
    }
  }

  .competitor-number {
    font-size: 24px;
    font-weight: bold;
  }

  .competitor-name {
    margin-top: 5px;
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
    margin-bottom: 15px;

    .rank-number {
      width: 60px;
      font-weight: bold;
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
    gap: 10px;
  }

  .competitor-card {
    .competitor-number {
      font-size: 20px;
    }
  }
}
</style>
