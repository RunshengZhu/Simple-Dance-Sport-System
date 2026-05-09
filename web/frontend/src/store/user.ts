import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login, getUserInfo } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref('')
  const role = ref('')

  const loginAction = async (username: string, password: string) => {
    const res: any = await login(username, password)
    token.value = res.access_token
    username.value = res.username
    role.value = res.role
    localStorage.setItem('token', res.access_token)
    return res
  }

  const logout = () => {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
  }

  return {
    token,
    username,
    role,
    loginAction,
    logout
  }
})
