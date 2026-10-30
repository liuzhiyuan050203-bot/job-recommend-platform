import request from '@/utils/request'

export function getMe() {
  return request({
    url: '/user/me',
    method: 'get'
  })
}

export function updatePassword(data) {
  return request({
    url: '/user/password',
    method: 'put',
    data
  })
}
