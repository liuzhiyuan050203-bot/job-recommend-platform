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
      const msg = res.msg || '请求失败'
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    return res
  },
  async (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const msg = data?.msg || data?.message || error.message || '网络连接异常'

    if (status === 401) {
      ElMessage.error(msg || '未登录或登录已过期')
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
      ElMessage.error(data?.msg || '无权限')
      return Promise.reject(error)
    }

    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default service
