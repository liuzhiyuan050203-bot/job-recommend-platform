import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8080',
  timeout: 10000
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    let token = ''
    try {
      const userStore = useUserStore()
      token = userStore.token
    } catch {
      // Pinia 未初始化时降级读取 localStorage
    }
    if (!token) {
      token = localStorage.getItem('token') || ''
    }

    if (token) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${token}`
      config.headers['token'] = token
    }
    return config
  },
  (error) => {
    console.error('Request Error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response) => {
    // 兼容 blob 或 arraybuffer 下载
    if (response.config.responseType === 'blob' || response.config.responseType === 'arraybuffer') {
      return response.data
    }

    const res = response.data

    // 统一处理 { code, msg, data } 结构
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code === 200) {
        return res.data
      }
      const msg = res.msg || res.message || '请求失败'
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }

    return res
  },
  (error) => {
    const msg = error.response?.data?.msg || error.response?.data?.message || error.message || '网络连接异常'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default service
