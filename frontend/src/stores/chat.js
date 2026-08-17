import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { streamChat, sendChat, fetchHistory, clearHistory } from '@/api/chat'
import { formatClock } from '@/utils/format'

const SESSION_KEY = 'drink_rag_sessions'
const ACTIVE_KEY = 'drink_rag_active_session'

let uid = 0
const nid = () => ++uid

function loadSessions() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY)) || [] } catch { return [] }
}

function saveSessions(list) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(list))
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessions: loadSessions(),          // [{ id, title, updated_at, turn_count }]
    sessionId: localStorage.getItem(ACTIVE_KEY) || 'default',
    messages: [],                      // { id, role, content, time, sources, streaming }
    pending: null,
    streaming: false,
    sessionsOpen: true,
    lastLatency: null,
    lastTokens: null
  }),
  getters: {
    hasMessages: (s) => s.messages.length > 0,
    currentSession: (s) => s.sessions.find((x) => x.id === s.sessionId) || null
  },
  actions: {
    // ---------- 会话管理 ----------
    _persistSession() {
      const idx = this.sessions.findIndex((x) => x.id === this.sessionId)
      const turns = this.messages.filter((m) => m.role === 'user').length
      const title = this.messages.find((m) => m.role === 'user')?.content.slice(0, 18) || '新对话'
      if (idx >= 0) {
        this.sessions[idx] = { ...this.sessions[idx], title, turn_count: turns, updated_at: Date.now() }
      } else {
        this.sessions.unshift({ id: this.sessionId, title, turn_count: turns, updated_at: Date.now() })
      }
      saveSessions(this.sessions.slice(0, 30))
    },
    setSession(id) {
      this.sessionId = id || 'default'
      localStorage.setItem(ACTIVE_KEY, this.sessionId)
    },
    newSession() {
      this.setSession(`s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`)
      this.messages = []
      this.pending = null
    },
    async switchSession(id) {
      if (id === this.sessionId) return
      this.setSession(id)
      await this.loadHistory()
    },
    async removeSession(id) {
      try { await clearHistory(id) } catch (e) { /* ignore */ }
      this.sessions = this.sessions.filter((x) => x.id !== id)
      saveSessions(this.sessions)
      if (this.sessionId === id) this.newSession()
    },
    toggleSessions() {
      this.sessionsOpen = !this.sessionsOpen
    },
    // ---------- 消息 ----------
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
        // 会话信息同步
        const turns = this.messages.filter((m) => m.role === 'user').length
        const title = this.messages.find((m) => m.role === 'user')?.content.slice(0, 18) || '新对话'
        const idx = this.sessions.findIndex((x) => x.id === this.sessionId)
        if (idx >= 0) {
          this.sessions[idx] = { ...this.sessions[idx], title, turn_count: turns, updated_at: Date.now() }
        } else if (turns > 0) {
          this.sessions.unshift({ id: this.sessionId, title, turn_count: turns, updated_at: Date.now() })
        }
        saveSessions(this.sessions.slice(0, 30))
      } catch (e) {
        console.warn('加载历史失败', e)
      }
    },
    async clear() {
      try { await clearHistory(this.sessionId) } catch (e) { /* ignore */ }
      this.messages = []
      this.pending = null
      const idx = this.sessions.findIndex((x) => x.id === this.sessionId)
      if (idx >= 0) this.sessions.splice(idx, 1)
      saveSessions(this.sessions)
    },
    // 流式发送
    async send(text, opts = {}) {
      if (this.streaming) return
      const { useHistory = true, showCitations = true } = opts
      const question = text.trim()
      if (!question) return

      const userMsg = reactive({ id: nid(), role: 'user', content: question, time: formatClock(Date.now()) })
      this.messages.push(userMsg)

      const botMsg = reactive({ id: nid(), role: 'assistant', content: '', time: formatClock(Date.now()), sources: [], streaming: true })
      this.pending = botMsg
      this.messages.push(botMsg)
      this.streaming = true
      this._persistSession()

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
            this._persistSession()
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
