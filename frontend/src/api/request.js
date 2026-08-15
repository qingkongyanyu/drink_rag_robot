import axios from 'axios'

// 统一 Axios 实例：错误拦截、携带业务 code
const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
    // 兼容后端两种返回结构：{code,msg,data} 与 {detail}
    if (body && typeof body === 'object' && 'code' in body && body.code !== 200) {
      return Promise.reject(new Error(body.msg || '请求失败'))
    }
    return body
  },
  (err) => {
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : detail?.msg || err.message || '网络异常'
    return Promise.reject(new Error(msg))
  }
)

// 带 FormData 上传的独立实例（自动 multipart）
export const uploadHttp = axios.create({
  baseURL: '/api',
  timeout: 300000,
  headers: { 'Content-Type': 'multipart/form-data' }
})
uploadHttp.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body && body.code !== 200) {
      return Promise.reject(new Error(body.msg || '上传失败'))
    }
    return body
  },
  (err) => Promise.reject(new Error(err.response?.data?.detail || err.message || '上传失败'))
)

export default http
