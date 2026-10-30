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
