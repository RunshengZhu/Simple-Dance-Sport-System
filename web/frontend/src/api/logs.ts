import request from './request'

export const getLogs = (params?: {
  user_id?: string
  action?: string
  resource?: string
  start_date?: string
  end_date?: string
  keyword?: string
  skip?: number
  limit?: number
}) => {
  return request.get('/logs/', { params })
}

export const getLogStats = (days?: number) => {
  return request.get('/logs/stats', { params: { days } })
}

export const getLogDetail = (logId: string) => {
  return request.get(`/logs/${logId}`)
}
