import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const request = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const message = error.response.data?.detail || '请求失败'

      if (status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('token')
        window.location.href = '/login'
      } else if (status === 403) {
        ElMessage.error(message || '没有权限')
      } else if (status === 404) {
        ElMessage.error('资源不存在')
      } else if (status >= 500) {
        ElMessage.error('服务器错误')
      } else {
        ElMessage.error(message)
      }
    } else {
      ElMessage.error('网络错误')
    }

    return Promise.reject(error)
  }
)

export default request
