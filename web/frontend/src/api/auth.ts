import request from './request'

// 用户登录API
export const login = (username: string, password: string) => {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  return request.post('/api/v1/auth/login', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 用户注册API
export const register = (username: string, password: string) => {
  return request.post('/api/v1/auth/register', null, {
    params: { username, password }
  })
}
