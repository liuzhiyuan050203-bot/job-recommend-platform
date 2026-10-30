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
