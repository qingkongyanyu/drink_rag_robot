import http from './request'

export function fetchStatus() {
  return http.get('/system/status')
}

export function fetchHealth() {
  return http.get('/system/health')
}

export function fetchDailyStats(days = 14) {
  return http.get('/system/stats/daily', { params: { days } })
}

export function fetchConfig() {
  return http.get('/system/config')
}
