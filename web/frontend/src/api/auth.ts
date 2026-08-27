import request from './request'

export const login = (username: string, password: string) => {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  return request.post('/auth/login', formData.toString(), {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

export const register = (username: string, password: string) => {
  return request.post('/auth/register', null, {
    params: { username, password }
  })
}

export const getMe = () => {
  return request.get('/auth/me')
}

export const logout = () => {
  return request.post('/auth/logout')
}

export const changePassword = (oldPassword: string, newPassword: string) => {
  return request.put('/auth/password', null, {
    params: { old_password: oldPassword, new_password: newPassword }
  })
}
