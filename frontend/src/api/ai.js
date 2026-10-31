import request from '@/utils/request'

export function listSessions(role, params) {
  return request({
    url: `/${role}/ai/sessions`,
    method: 'get',
    params
  })
}

export function listMessages(role, sessionId) {
  return request({
    url: `/${role}/ai/sessions/${sessionId}/messages`,
    method: 'get'
  })
}

export function deleteSession(role, sessionId) {
  return request({
    url: `/${role}/ai/sessions/${sessionId}`,
    method: 'delete'
  })
}

export function renameSession(role, sessionId, title) {
  return request({
    url: `/${role}/ai/sessions/${sessionId}`,
    method: 'put',
    data: { title }
  })
}

export function streamUrl(role) {
  return `/api/${role}/ai/chat/stream`
}

export function knowledgeDocuments(params) {
  return request({
    url: '/admin/ai/knowledge/documents',
    method: 'get',
    params
  })
}

export function knowledgeStats() {
  return request({
    url: '/admin/ai/knowledge/stats',
    method: 'get'
  })
}

export function uploadKnowledge(formData) {
  return request({
    url: '/admin/ai/knowledge/upload',
    method: 'post',
    data: formData,
    timeout: 120000
  })
}

export function reindexKnowledge(params) {
  return request({
    url: '/admin/ai/knowledge/reindex',
    method: 'post',
    params,
    timeout: 300000
  })
}

export function deleteKnowledge(docKey) {
  return request({
    url: '/admin/ai/knowledge/documents',
    method: 'delete',
    params: { docKey }
  })
}

export function searchKnowledge(params) {
  return request({
    url: '/admin/ai/knowledge/search',
    method: 'get',
    params,
    timeout: 60000
  })
}
