import request from './request'

export const getEvents = (competitionId: string) => {
  return request.get(`/competitions/${competitionId}/events`)
}

export const getEventDetails = (eventId: string) => {
  return request.get(`/events/${eventId}`)
}

export const getCompetitors = (competitionId: string, competitorNumbers?: string[]) => {
  return request.get(`/competitions/${competitionId}/competitors`, {
    params: { numbers: competitorNumbers?.join(',') }
  })
}

export const getScores = (eventId: string, judgeId: string) => {
  return request.get(`/events/${eventId}/scores`, {
    params: { judge_id: judgeId }
  })
}

export const submitScores = (eventId: string, data: any[]) => {
  return request.post(`/events/${eventId}/scores`, data)
}

export const getResults = (eventId: string) => {
  return request.get(`/events/${eventId}/results`)
}

export const getScoreDetails = (eventId: string) => {
  return request.get(`/events/${eventId}/score-details`)
}

export const calculateResults = (eventId: string) => {
  return request.post(`/events/${eventId}/calculate`)
}
