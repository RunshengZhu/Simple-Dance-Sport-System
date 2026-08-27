import request from './request'

// 获取场次列表
export const getEvents = (competitionId: string) => {
  return request.get(`/api/v1/competitions/${competitionId}/events`)
}

// 获取场次详情
export const getEvent = (id: string) => {
  return request.get(`/api/v1/events/${id}`)
}

// 创建场次
export const createEvent = (competitionId: string, data: any) => {
  return request.post(`/api/v1/competitions/${competitionId}/events`, data)
}

// 更新场次
export const updateEvent = (id: string, data: any) => {
  return request.put(`/api/v1/events/${id}`, data)
}

// 删除场次
export const deleteEvent = (competitionId: string, id: string) => {
  return request.delete(`/api/v1/events/${id}`)
}

// 开始场次评分
export const startEvent = (id: string) => {
  return request.post(`/api/v1/events/${id}/start`)
}

// 完成场次评分
export const completeEvent = (id: string) => {
  return request.post(`/api/v1/events/${id}/complete`)
}

// 导入赛程
export const importSchedule = (competitionId: string, file: FormData) => {
  return request.post(`/api/v1/competitions/${competitionId}/import-schedule`, file, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// 导入测试数据
export const setupFromTestData = (competitionId: string) => {
  return request.post(`/api/v1/competitions/${competitionId}/setup-from-test-data`)
}
