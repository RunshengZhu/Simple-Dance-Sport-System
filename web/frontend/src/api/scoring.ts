import request from './request'

// 获取评分列表
export const getScores = (eventId: string) => {
  return request.get(`/api/v1/events/${eventId}/scores`)
}

// 提交评分
export const submitScores = (eventId: string, data: any[]) => {
  return request.post(`/api/v1/events/${eventId}/scores`, data)
}

// 获取比赛结果
export const getResults = (eventId: string, danceName?: string) => {
  return request.get(`/api/v1/events/${eventId}/results`, { params: { dance_name: danceName } })
}

// 计算比赛结果
export const calculateResults = (eventId: string) => {
  return request.post(`/api/v1/events/${eventId}/calculate`)
}
