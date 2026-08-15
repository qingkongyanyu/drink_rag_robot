import { defineStore } from 'pinia'
import { streamChat, sendChat, fetchHistory, clearHistory } from '@/api/chat'
import { formatClock } from '@/utils/format'

const STORAGE_KEY = 'drink_rag_session'

let uid = 0
const nid = () => ++uid

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessionId: localStorage.getItem(STORAGE_KEY) || 'default',
    messages: [],          // { id, role, content, time, sources, streaming }
    pending: null,         // 正在流式生成的助手消息对象
    streaming: false,
    lastLatency: null,
    lastTokens: null
  }),
  getters: {
    hasMessages: (s) => s.messages.length > 0
  },
  actions: {
    setSession(id) {
      this.sessionId = id || 'default'
      localStorage.setItem(STORAGE_KEY, this.sessionId)
    },
    async loadHistory() {
      try {
        const res = await fetchHistory(this.sessionId)
        const list = res.data || []
        this.messages = list
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({
            id: nid(),
            role: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
            time: formatClock(m.created_at * 1000),
            sources: m.sources || []
          }))
      } catch (e) {
        console.warn('加载历史失败', e)
      }
    },
    async clear() {
      try { await clearHistory(this.sessionId) } catch (e) { /* ignore */ }
      this.messages = []
      this.pending = null
    },
    // 流式发送
    async send(text, opts = {}) {
      if (this.streaming) return
      const { useHistory = true, showCitations = true } = opts
      const question = text.trim()
      if (!question) return

      const userMsg = { id: nid(), role: 'user', content: question, time: formatClock(Date.now()) }
      this.messages.push(userMsg)

      const botMsg = { id: nid(), role: 'assistant', content: '', time: formatClock(Date.now()), sources: [], streaming: true }
      this.pending = botMsg
      this.messages.push(botMsg)
      this.streaming = true

      const payload = {
        session_id: this.sessionId,
        question,
        use_history: useHistory,
        show_citations: showCitations
      }

      try {
        await streamChat(payload, {
          onMeta: (ev) => { botMsg.sources = ev.sources || []; botMsg.useKnowledge = ev.use_knowledge },
          onDelta: (chunk) => { botMsg.content += chunk },
          onDone: (ev) => {
            botMsg.streaming = false
            botMsg.latency = ev.latency_ms
            this.lastLatency = ev.latency_ms
            this.lastTokens = ev.llm_tokens
          },
          onError: (msg) => {
            botMsg.streaming = false
            botMsg.content = `⚠️ ${msg}`
          }
        })
      } catch (err) {
        botMsg.streaming = false
        botMsg.content = `⚠️ ${err.message}`
      } finally {
        this.streaming = false
        this.pending = null
      }
    }
  }
})
