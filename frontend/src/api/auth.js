import request from '@/utils/request'

export function login(data) {
  return request({
    url: '/public/auth/login',
    method: 'post',
    data
  })
}

export function registerStudent(data) {
  return request({
    url: '/public/auth/register/student',
    method: 'post',
    data
  })
}

export function registerCompany(data) {
  return request({
    url: '/public/auth/register/company',
    method: 'post',
    data
  })
}
