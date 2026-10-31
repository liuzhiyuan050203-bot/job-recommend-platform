import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

function displayMessage(text, fallback) {
  const value = String(text || '').trim()
  if (value && /[\u4e00-\u9fff]/.test(value)) {
    return value
  }
  return fallback
}

async function clearSession() {
  try {
    const { useUserStore } = await import('@/stores/user')
    useUserStore().logout()
  } catch {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('role')
  }
}

service.interceptors.response.use(
  (response) => {
    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response.data
    }
    const res = response.data
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code === 200) {
        return res.data
      }
      const msg = displayMessage(res.msg, '请求失败')
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    return res
  },
  async (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const backendMsg = data && typeof data === 'object' ? (data.msg || data.message) : ''

    if (status === 401) {
      ElMessage.error('未登录或登录已过期')
      await clearSession()
      try {
        const { default: router } = await import('@/router')
        if (router.currentRoute.value.path !== '/login') {
          const redirect = router.currentRoute.value.fullPath
          router.push({
            path: '/login',
            query: redirect && redirect !== '/' ? { redirect } : {}
          })
        }
      } catch {
        // 路由未就绪时只清理登录态
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      ElMessage.error(displayMessage(backendMsg, '无权限'))
      return Promise.reject(error)
    }

    const timedOut = error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '')
    const fallback = !error.response
      ? (timedOut ? '请求超时，请稍后重试' : '网络连接异常')
      : '请求失败'
    ElMessage.error(displayMessage(backendMsg, fallback))
    return Promise.reject(error)
  }
)

export default service
