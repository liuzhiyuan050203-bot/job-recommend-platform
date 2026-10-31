import request from '@/utils/request'

export function getStudentProfile() {
  return request({
    url: '/student/profile',
    method: 'get'
  })
}

export function updateStudentProfile(data) {
  return request({
    url: '/student/profile',
    method: 'put',
    data
  })
}

export function getStudentSkills() {
  return request({
    url: '/student/skills',
    method: 'get'
  })
}

export function addStudentSkill(data) {
  return request({
    url: '/student/skills',
    method: 'post',
    data
  })
}

export function updateStudentSkill(id, data) {
  return request({
    url: `/student/skills/${id}`,
    method: 'put',
    data
  })
}

export function deleteStudentSkill(id) {
  return request({
    url: `/student/skills/${id}`,
    method: 'delete'
  })
}

export function getMyPosts(params) {
  return request({
    url: '/student/posts',
    method: 'get',
    params
  })
}

export function createPost(data) {
  return request({
    url: '/student/posts',
    method: 'post',
    data
  })
}

export function updatePost(id, data) {
  return request({
    url: `/student/posts/${id}`,
    method: 'put',
    data
  })
}

export function deletePost(id) {
  return request({
    url: `/student/posts/${id}`,
    method: 'delete'
  })
}

export function addComment(postId, data) {
  return request({
    url: `/student/posts/${postId}/comments`,
    method: 'post',
    data
  })
}

export function deleteComment(id) {
  return request({
    url: `/student/comments/${id}`,
    method: 'delete'
  })
}

export function getResumes() {
  return request({ url: '/student/resumes', method: 'get' })
}

export function getResume(id) {
  return request({ url: `/student/resumes/${id}`, method: 'get' })
}

export function createResume(data) {
  return request({ url: '/student/resumes', method: 'post', data })
}

export function updateResume(id, data) {
  return request({ url: `/student/resumes/${id}`, method: 'put', data })
}

export function setDefaultResume(id) {
  return request({ url: `/student/resumes/${id}/default`, method: 'put' })
}

export function deleteResume(id) {
  return request({ url: `/student/resumes/${id}`, method: 'delete' })
}

export function getFavorites(params) {
  return request({ url: '/student/favorites', method: 'get', params })
}

export function addFavorite(jobId) {
  return request({ url: '/student/favorites', method: 'post', data: { jobId } })
}

export function removeFavorite(jobId) {
  return request({ url: `/student/favorites/${jobId}`, method: 'delete' })
}

export function applyJob(data) {
  return request({ url: '/student/applications', method: 'post', data })
}

export function getApplications(params) {
  return request({ url: '/student/applications', method: 'get', params })
}

export function getApplication(id) {
  return request({ url: `/student/applications/${id}`, method: 'get' })
}

export function getUpcomingInterviews() {
  return request({ url: '/student/interviews/upcoming', method: 'get' })
}

export function getRecommendations(params) {
  return request({ url: '/student/recommend', method: 'get', params })
}

export function getStudentDashboard() {
  return request({ url: '/student/dashboard', method: 'get' })
}
