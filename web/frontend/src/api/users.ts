import request from './request'

export interface User {
  id: string
  username: string
  role: string
  full_name?: string
  email?: string
  phone?: string
  is_active: boolean
  created_at: string
  last_login?: string
}

export interface UserQuery {
  role?: string
  is_active?: boolean
  keyword?: string
  skip?: number
  limit?: number
}

export const getUsers = (params: UserQuery) => {
  return request.get('/users/', { params })
}

export const getUser = (userId: string) => {
  return request.get(`/users/${userId}`)
}

export const createUser = (data: {
  username: string
  password: string
  role?: string
  full_name?: string
  email?: string
  phone?: string
}) => {
  return request.post('/users/', data)
}

export const updateUser = (userId: string, data: Partial<User>) => {
  return request.put(`/users/${userId}`, data)
}

export const deleteUser = (userId: string) => {
  return request.delete(`/users/${userId}`)
}

export const resetPassword = (userId: string, newPassword: string) => {
  return request.put(`/users/${userId}/reset-password`, null, {
    params: { new_password: newPassword }
  })
}

export const getRoles = () => {
  return request.get('/users/roles/list')
}
