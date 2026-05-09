import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userName = ref('')
  const role = ref('')

  const loginAction = async (name: string, pwd: string) => {
    const res: any = await login(name, pwd)
    token.value = res.access_token
    userName.value = res.username
    role.value = res.role
    localStorage.setItem('token', res.access_token)
    return res
  }

  const logout = () => {
    token.value = ''
    userName.value = ''
    role.value = ''
    localStorage.removeItem('token')
  }

  return {
    token,
    userName,
    role,
    loginAction,
    logout
  }
})
