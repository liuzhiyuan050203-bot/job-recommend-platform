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

export function getCompanyJobs(params) {
  return request({ url: '/company/jobs', method: 'get', params })
}

export function getCompanyJob(id) {
  return request({ url: `/company/jobs/${id}`, method: 'get' })
}

export function createCompanyJob(data) {
  return request({ url: '/company/jobs', method: 'post', data })
}

export function updateCompanyJob(id, data) {
  return request({ url: `/company/jobs/${id}`, method: 'put', data })
}

export function shelfCompanyJob(id, shelfStatus) {
  return request({ url: `/company/jobs/${id}/shelf`, method: 'put', data: { shelfStatus } })
}

export function deleteCompanyJob(id) {
  return request({ url: `/company/jobs/${id}`, method: 'delete' })
}

export function getCompanyApplications(params) {
  return request({ url: '/company/applications', method: 'get', params })
}

export function getCompanyApplication(id) {
  return request({ url: `/company/applications/${id}`, method: 'get' })
}

export function updateApplicationStatus(id, data) {
  return request({ url: `/company/applications/${id}/status`, method: 'put', data })
}

export function sendInterviewNotice(id, data) {
  return request({ url: `/company/applications/${id}/interviews`, method: 'post', data })
}

export function getCompanyInterviews(params) {
  return request({ url: '/company/interviews', method: 'get', params })
}

export function saveInterviewResult(id, data) {
  return request({ url: `/company/interviews/${id}/result`, method: 'put', data })
}

export function getCompanyDashboard() {
  return request({ url: '/company/dashboard', method: 'get' })
}
