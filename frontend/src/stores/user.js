import { defineStore } from 'pinia'
import { login as loginApi } from '@/api/auth'
import { getMe } from '@/api/user'

function readSession() {
  const token = localStorage.getItem('token') || ''
  let userInfo = null
  try {
    const raw = localStorage.getItem('userInfo')
    if (raw) {
      userInfo = JSON.parse(raw)
    }
  } catch {
    userInfo = null
  }
  if (!token || !userInfo || !userInfo.roleName) {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('role')
    return { token: '', userInfo: null }
  }
  return { token, userInfo }
}

const session = readSession()

export const useUserStore = defineStore('user', {
  state: () => ({
    token: session.token,
    userInfo: session.userInfo
  }),

  getters: {
    isLoggedIn: (state) => !!state.token && !!state.userInfo?.roleName,
    roleName: (state) => state.userInfo?.roleName || '',
    nickname: (state) => state.userInfo?.nickname || state.userInfo?.username || '用户',
    companyAuditStatus: (state) => state.userInfo?.companyAuditStatus
  },

  actions: {
    setSession(token, userInfo) {
      this.token = token || ''
      this.userInfo = userInfo || null
      if (this.token && this.userInfo) {
        localStorage.setItem('token', this.token)
        localStorage.setItem('userInfo', JSON.stringify(this.userInfo))
      } else {
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
      }
      localStorage.removeItem('role')
    },

    async login(payload) {
      const data = await loginApi(payload)
      this.setSession(data.token, data.user)
      return data
    },

    async fetchMe() {
      const data = await getMe()
      this.userInfo = data
      localStorage.setItem('userInfo', JSON.stringify(data))
      return data
    },

    logout() {
      this.token = ''
      this.userInfo = null
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      localStorage.removeItem('role')
    }
  }
})
