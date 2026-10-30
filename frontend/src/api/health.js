import request from '@/utils/request'

/**
 * 获取系统健康状态（包含后端服务、db、aiService等）
 * baseURL 已是 /api，这里只写 /health
 */
export function getHealth() {
  return request({
    url: '/health',
    method: 'get'
  })
}
