import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    role: localStorage.getItem('role') || '',
    userInfo: (() => {
      try {
        return JSON.parse(localStorage.getItem('userInfo') || '{}')
      } catch {
        return {}
      }
    })()
  }),

  getters: {
    isLoggedIn: (state) => !!state.token
  },

  actions: {
    setToken(token) {
      this.token = token || ''
      if (token) {
        localStorage.setItem('token', token)
      } else {
        localStorage.removeItem('token')
      }
    },

    setRole(role) {
      this.role = role || ''
      if (role) {
        localStorage.setItem('role', role)
      } else {
        localStorage.removeItem('role')
      }
    },

    setUserInfo(info) {
      this.userInfo = info || {}
      localStorage.setItem('userInfo', JSON.stringify(this.userInfo))
    },

    login({ token, role, userInfo }) {
      if (token) this.setToken(token)
      if (role) this.setRole(role)
      if (userInfo) this.setUserInfo(userInfo)
    },

    logout() {
      this.token = ''
      this.role = ''
      this.userInfo = {}
      localStorage.removeItem('token')
      localStorage.removeItem('role')
      localStorage.removeItem('userInfo')
    }
  }
})
