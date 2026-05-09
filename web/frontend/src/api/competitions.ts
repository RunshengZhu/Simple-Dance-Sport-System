import request from './request'

// 获取赛事列表
export const getCompetitions = (params?: any) => {
  return request.get('/api/v1/competitions', { params })
}

// 获取赛事详情
export const getCompetition = (id: string) => {
  return request.get(`/api/v1/competitions/${id}`)
}

// 创建赛事
export const createCompetition = (data: any) => {
  return request.post('/api/v1/competitions', data)
}

// 更新赛事
export const updateCompetition = (id: string, data: any) => {
  return request.put(`/api/v1/competitions/${id}`, data)
}

// 删除赛事
export const deleteCompetition = (id: string) => {
  return request.delete(`/api/v1/competitions/${id}`)
}
