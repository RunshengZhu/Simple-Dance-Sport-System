import request from './request'

// 获取选手列表
export const getCompetitors = (competitionId: string) => {
  return request.get(`/api/v1/competitions/${competitionId}/competitors`)
}

// 创建选手
export const createCompetitor = (competitionId: string, data: any) => {
  return request.post(`/api/v1/competitions/${competitionId}/competitors`, data)
}

// 更新选手
export const updateCompetitor = (competitionId: string, id: string, data: any) => {
  return request.put(`/api/v1/competitions/${competitionId}/competitors/${id}`, data)
}

// 删除选手
export const deleteCompetitor = (competitionId: string, id: string) => {
  return request.delete(`/api/v1/competitions/${competitionId}/competitors/${id}`)
}
