import http, { uploadHttp } from './request'

export function fetchDocs() {
  return http.get('/knowledge/docs')
}

export function uploadFiles(files, category) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  form.append('category', category)
  return uploadHttp.post('/knowledge/upload', form)
}

export function fetchDocDetail(docId) {
  return http.get(`/knowledge/docs/${docId}`)
}

export function deleteDoc(docId) {
  return http.delete(`/knowledge/docs/${docId}`)
}

export function searchKnowledge(query, topK = 8) {
  return http.post('/knowledge/search', { query, top_k: topK })
}

export function fetchKnowledgeStats() {
  return http.get('/knowledge/stats')
}
