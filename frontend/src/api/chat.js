import http from './request'

// 普通问答
export function sendChat(payload) {
  return http.post('/chat', { ...payload, stream: false })
}

/**
 * SSE 流式问答：解析事件流，逐段回调。
 *
 * 兼容两种 SSE 形态：
 *   A) event: meta\n data: {...}          （类型在 event: 行，data 无 type）
 *   B) data: {"type":"meta", ...}          （类型在 data.type 内）
 * 统一按「event 名 || data.type」分发。
 */
export async function streamChat(payload, handlers = {}) {
  const { onMeta, onDelta, onDone, onError } = handlers
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true })
  })
  if (!resp.ok) {
    let msg = `请求失败 (${resp.status})`
    try {
      const j = await resp.json()
      msg = j.detail || msg
    } catch (e) { /* ignore */ }
    throw new Error(msg)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  // 单个 SSE 块：可能含 event: 行 + data: 行
  const dispatchBlock = (block) => {
    let eventName = ''
    let dataStr = ''
    for (const line of block.split('\n')) {
      const t = line.trim()
      if (t.startsWith('event:')) eventName = t.slice(6).trim()
      else if (t.startsWith('data:')) dataStr = t.slice(5).trim()
    }
    if (!dataStr || dataStr === '[DONE]') return
    let evt
    try { evt = JSON.parse(dataStr) } catch { return }
    const type = evt.type || eventName
    if (type === 'meta') onMeta?.(evt)
    else if (type === 'delta') onDelta?.(evt.content || '')
    else if (type === 'done') onDone?.(evt)
    else if (type === 'error') onError?.(evt.message || '生成失败')
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 以空行分隔
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      if (block.trim()) dispatchBlock(block)
    }
  }
  if (buffer.trim()) dispatchBlock(buffer)
}

export function fetchHistory(sessionId) {
  return http.get('/chat/history', { params: { session_id: sessionId } })
}

export function clearHistory(sessionId) {
  return http.post('/chat/clear', { session_id: sessionId })
}
