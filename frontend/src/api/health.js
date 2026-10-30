import request from '@/utils/request'

/**
 * 获取系统健康状态（包含后端服务、db、aiService等）
 */
export function getHealth() {
  return request({
    url: '/api/health',
    method: 'get'
  })
}
