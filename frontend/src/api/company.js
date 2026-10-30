import request from '@/utils/request'

export function getCompanyProfile() {
  return request({
    url: '/company/profile',
    method: 'get'
  })
}

export function updateCompanyProfile(data) {
  return request({
    url: '/company/profile',
    method: 'put',
    data
  })
}

export function submitCompanyQualification(data) {
  return request({
    url: '/company/profile/qualification',
    method: 'post',
    data
  })
}
