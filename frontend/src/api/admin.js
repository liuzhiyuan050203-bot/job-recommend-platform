import request from '@/utils/request'

// 用户管理
export function getAdminUsers(params) {
  return request({
    url: '/admin/users',
    method: 'get',
    params
  })
}

export function updateAdminUserStatus(id, status) {
  return request({
    url: `/admin/users/${id}/status`,
    method: 'put',
    data: { status }
  })
}

export function resetAdminUserPassword(id) {
  return request({
    url: `/admin/users/${id}/reset-password`,
    method: 'put'
  })
}

// 企业资质审核
export function getAdminCompanies(params) {
  return request({
    url: '/admin/companies',
    method: 'get',
    params
  })
}

export function getAdminCompany(id) {
  return request({
    url: `/admin/companies/${id}`,
    method: 'get'
  })
}

export function auditAdminCompany(id, data) {
  return request({
    url: `/admin/companies/${id}/audit`,
    method: 'put',
    data
  })
}

// 职位审核
export function getAdminJobs(params) {
  return request({
    url: '/admin/jobs',
    method: 'get',
    params
  })
}

export function auditAdminJob(id, data) {
  return request({
    url: `/admin/jobs/${id}/audit`,
    method: 'put',
    data
  })
}

// 社区面经与评论审核
export function getAdminPosts(params) {
  return request({
    url: '/admin/posts',
    method: 'get',
    params
  })
}

export function auditAdminPost(id, data) {
  return request({
    url: `/admin/posts/${id}/audit`,
    method: 'put',
    data
  })
}

export function deleteAdminPost(id) {
  return request({
    url: `/admin/posts/${id}`,
    method: 'delete'
  })
}

export function getAdminComments(params) {
  return request({
    url: '/admin/comments',
    method: 'get',
    params
  })
}

export function auditAdminComment(id, data) {
  return request({
    url: `/admin/comments/${id}/audit`,
    method: 'put',
    data
  })
}

export function deleteAdminComment(id) {
  return request({
    url: `/admin/comments/${id}`,
    method: 'delete'
  })
}

// 轮播图管理
export function getAdminBanners(params) {
  return request({
    url: '/admin/banners',
    method: 'get',
    params
  })
}

export function addAdminBanner(data) {
  return request({
    url: '/admin/banners',
    method: 'post',
    data
  })
}

export function updateAdminBanner(id, data) {
  return request({
    url: `/admin/banners/${id}`,
    method: 'put',
    data
  })
}

export function deleteAdminBanner(id) {
  return request({
    url: `/admin/banners/${id}`,
    method: 'delete'
  })
}

// 文章资讯管理
export function getAdminArticles(params) {
  return request({
    url: '/admin/articles',
    method: 'get',
    params
  })
}

export function getAdminArticle(id) {
  return request({
    url: `/admin/articles/${id}`,
    method: 'get'
  })
}

export function addAdminArticle(data) {
  return request({
    url: '/admin/articles',
    method: 'post',
    data
  })
}

export function updateAdminArticle(id, data) {
  return request({
    url: `/admin/articles/${id}`,
    method: 'put',
    data
  })
}

export function updateAdminArticleStatus(id, status) {
  return request({
    url: `/admin/articles/${id}/status`,
    method: 'put',
    data: { status }
  })
}

export function deleteAdminArticle(id) {
  return request({
    url: `/admin/articles/${id}`,
    method: 'delete'
  })
}

// 职位分类管理
export function getAdminCategories() {
  return request({
    url: '/admin/categories',
    method: 'get'
  })
}

export function addAdminCategory(data) {
  return request({
    url: '/admin/categories',
    method: 'post',
    data
  })
}

export function updateAdminCategory(id, data) {
  return request({
    url: `/admin/categories/${id}`,
    method: 'put',
    data
  })
}

export function deleteAdminCategory(id) {
  return request({
    url: `/admin/categories/${id}`,
    method: 'delete'
  })
}

// 技能标签管理
export function getAdminSkillTags(params) {
  return request({
    url: '/admin/skill-tags',
    method: 'get',
    params
  })
}

export function addAdminSkillTag(data) {
  return request({
    url: '/admin/skill-tags',
    method: 'post',
    data
  })
}

export function updateAdminSkillTag(id, data) {
  return request({
    url: `/admin/skill-tags/${id}`,
    method: 'put',
    data
  })
}

export function deleteAdminSkillTag(id) {
  return request({
    url: `/admin/skill-tags/${id}`,
    method: 'delete'
  })
}

export function getAdminOverview() {
  return request({ url: '/admin/overview', method: 'get' })
}

export function getAdminApplications(params) {
  return request({ url: '/admin/applications', method: 'get', params })
}

export function runSparkAnalysis(data) {
  return request({
    url: '/admin/spark/run',
    method: 'post',
    data: data || {},
    timeout: 30000
  })
}

export function getSparkTasks(params) {
  return request({ url: '/admin/spark/tasks', method: 'get', params })
}

export function runRecommend() {
  return request({
    url: '/admin/recommend/run',
    method: 'post',
    data: {},
    timeout: 30000
  })
}

export function getRecommendEval() {
  return request({ url: '/admin/recommend/eval', method: 'get' })
}

export function getRecommendStats() {
  return request({ url: '/admin/recommend/stats', method: 'get' })
}

export function getAdminDashboard() {
  return request({ url: '/admin/dashboard/overview', method: 'get' })
}
