import request from './request'

// 获取单位排名
export const getRanking = (competitionId: string) => {
  return request.get(`/api/v1/competitions/${competitionId}/ranking`)
}

// 获取奖项配置
export const getAwardConfig = (eventId: string) => {
  return request.get(`/api/v1/events/${eventId}/award-config`)
}

// 更新奖项配置
export const updateAwardConfig = (eventId: string, points: Record<string, number>) => {
  return request.put(`/api/v1/events/${eventId}/award-config`, { event_id: eventId, points })
}
