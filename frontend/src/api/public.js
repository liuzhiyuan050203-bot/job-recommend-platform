import request from '@/utils/request'

export function getBanners() {
  return request({
    url: '/public/banners',
    method: 'get'
  })
}

export function getArticles(params) {
  return request({
    url: '/public/articles',
    method: 'get',
    params
  })
}

export function getArticle(id) {
  return request({
    url: `/public/articles/${id}`,
    method: 'get'
  })
}

export function getCategories() {
  return request({
    url: '/public/categories',
    method: 'get'
  })
}

export function getSkillTags(direction) {
  return request({
    url: '/public/skill-tags',
    method: 'get',
    params: { direction }
  })
}

export function getPosts(params) {
  return request({
    url: '/public/posts',
    method: 'get',
    params
  })
}

export function getPost(id) {
  return request({
    url: `/public/posts/${id}`,
    method: 'get'
  })
}

export function searchJobs(params) {
  return request({
    url: '/public/jobs',
    method: 'get',
    params
  })
}

export function getJob(id) {
  return request({
    url: `/public/jobs/${id}`,
    method: 'get'
  })
}

export function getSimilarJobs(id, size = 6) {
  return request({
    url: `/public/jobs/${id}/similar`,
    method: 'get',
    params: { size }
  })
}

export function getStatsOverview() {
  return request({ url: '/public/stats/overview', method: 'get' })
}

export function getSalaryStats(params) {
  return request({ url: '/public/stats/salary', method: 'get', params })
}

export function getTechTrend(params) {
  return request({ url: '/public/stats/tech-trend', method: 'get', params })
}

export function getRegionStats() {
  return request({ url: '/public/stats/region', method: 'get' })
}

export function getHiringDemand(params) {
  return request({ url: '/public/stats/hiring-demand', method: 'get', params })
}

export function predictSalary(params) {
  return request({ url: '/public/stats/salary/predict', method: 'get', params })
}
