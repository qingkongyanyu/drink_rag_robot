<template>
  <div class="chat-view">
    <!-- ===== 顶栏 ===== -->
    <header class="chat-top">
      <div class="top-left">
        <button class="icon-btn" @click="chat.toggleSessions" title="会话列表">
          <i class="fa-solid" :class="chat.sessionsOpen ? 'fa-panel-left' : 'fa-panel-left'"></i>
          <i class="fa-solid fa-bars"></i>
        </button>
        <div class="peer-avatar">
          <img src="@/assets/bot-avatar.png" alt="机器人" class="avatar-img" />
        </div>
        <div class="peer-info">
          <div class="peer-name">饮料健康智能顾问</div>
          <div class="peer-status">
            <i class="fa-solid fa-circle" :class="system.online ? 'online' : 'offline'"></i>
            {{ system.online ? '在线 · 高级RAG · 千问大模型' : '离线' }}
          </div>
        </div>
      </div>
      <div class="top-right">
        <span class="chip model-chip" title="当前大模型">
          <i class="fa-solid fa-microchip"></i>{{ system.status?.llm_model || 'qwen' }}
        </span>
        <button class="btn btn-primary btn-sm" @click="chat.newSession">
          <i class="fa-solid fa-plus"></i><span>新对话</span>
        </button>
        <button class="icon-btn" @click="confirmClear" :disabled="!chat.hasMessages" title="清空当前会话">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </div>
    </header>

    <div class="chat-body">
      <!-- ===== 会话列表面板 ===== -->
      <aside v-show="chat.sessionsOpen" class="session-panel">
        <div class="session-head">
          <span>历史会话</span>
          <span class="session-count">{{ chat.sessions.length }}</span>
        </div>
        <div class="session-list">
          <button
            v-for="s in chat.sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === chat.sessionId }"
            @click="chat.switchSession(s.id)"
          >
            <i class="fa-regular fa-comment-dots sess-icon"></i>
            <div class="sess-info">
              <div class="sess-title">{{ s.title }}</div>
              <div class="sess-meta">{{ s.turn_count || 0 }} 轮 · {{ formatTime(s.updated_at) }}</div>
            </div>
            <button class="sess-del" title="删除" @click.stop="chat.removeSession(s.id)">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </button>
          <div v-if="!chat.sessions.length" class="session-empty">
            暂无历史会话<br />发送一条消息试试
          </div>
        </div>
      </aside>

      <!-- ===== 消息区 ===== -->
      <div class="chat-scroll" ref="scrollRef">
        <!-- 欢迎卡片 -->
        <div v-if="!chat.hasMessages && !chat.streaming" class="welcome">
          <div class="welcome-logo">
            <img src="@/assets/bot-avatar.png" alt="机器人" class="avatar-img" />
          </div>
          <h1 class="welcome-title">饮料健康智能顾问</h1>
          <p class="welcome-desc">
            内置 100 款超市常见饮料知识库，<b>语义向量 + 关键词</b>混合检索 + <b>交叉编码器重排</b>，严格依据知识回答。
          </p>
          <div class="welcome-cards">
            <button class="wc-card" @click="quick('可乐含糖量高吗？糖尿病人能喝吗？')">
              <i class="fa-solid fa-cube"></i><span>可乐糖分 · 糖尿病人</span>
            </button>
            <button class="wc-card" @click="quick('虚寒体质适合喝什么饮料？')">
              <i class="fa-solid fa-snowflake"></i><span>虚寒体质饮品</span>
            </button>
            <button class="wc-card" @click="quick('夏天有什么清爽低卡的饮料推荐？')">
              <i class="fa-solid fa-sun"></i><span>夏季低卡推荐</span>
            </button>
            <button class="wc-card" @click="quick('红牛长期饮用有什么副作用？')">
              <i class="fa-solid fa-bolt"></i><span>红牛副作用</span>
            </button>
          </div>
        </div>

        <!-- 消息列表（微信气泡） -->
        <div v-else class="msg-list">
          <MessageItem v-for="m in chat.messages" :key="m.id" :msg="m" />
        </div>
      </div>
    </div>

    <!-- ===== 输入区 ===== -->
    <footer class="chat-input-area">
      <div class="input-tools">
        <button class="tool-btn" :class="{ active: useHistory }" @click="useHistory = !useHistory" title="多轮上下文记忆">
          <i class="fa-solid fa-clock-rotate-left"></i> 记忆
        </button>
        <button class="tool-btn" :class="{ active: showCitations }" @click="showCitations = !showCitations" title="回答附带来源引用">
          <i class="fa-solid fa-quote-right"></i> 引用
        </button>
        <span class="char-count" :class="{ over: input.length > MAX }">{{ input.length }}/{{ MAX }}</span>
      </div>
      <div class="input-wrap">
        <textarea
          ref="taRef"
          v-model="input"
          rows="1"
          :placeholder="placeholder"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
        ></textarea>
        <button class="send-btn" :disabled="chat.streaming || !input.trim()" @click="send">
          <i v-if="chat.streaming" class="fa-solid fa-circle-notch fa-spin"></i>
          <i v-else class="fa-solid fa-paper-plane"></i>
        </button>
      </div>
      <div class="input-hint">Enter 发送 · Shift+Enter 换行</div>
    </footer>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import MessageItem from '@/components/MessageItem.vue'
import { useChatStore } from '@/stores/chat'
import { useSystemStore } from '@/stores/system'

const chat = useChatStore()
const system = useSystemStore()
const input = ref('')
const MAX = 800
const useHistory = ref(true)
const showCitations = ref(true)
const scrollRef = ref(null)
const taRef = ref(null)

const placeholder = '输入你想咨询的饮料健康问题…'

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function autoResize() {
  const ta = taRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 150) + 'px'
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || chat.streaming) return
  if (text.length > MAX) return
  input.value = ''
  autoResize()
  await chat.send(text, { useHistory: useHistory.value, showCitations: showCitations.value })
  scrollToBottom()
}

function quick(text) {
  input.value = text
  send()
}

function confirmClear() {
  chat.clear()
}

watch(
  () => chat.messages.length,
  () => scrollToBottom()
)

onMounted(async () => {
  await chat.loadHistory()
  scrollToBottom()
  taRef.value?.focus()
})
</script>

<style scoped>
.chat-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--chat-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow);
}

/* ---------- 顶栏 ---------- */
.chat-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
  background: var(--glass);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 10px;
}
.top-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.icon-btn {
  width: 34px; height: 34px; flex-shrink: 0;
  display: grid; place-items: center;
  border-radius: 10px;
  background: var(--glass-strong);
  border: 1px solid var(--border);
  color: var(--text-sub);
  font-size: 14px;
  transition: all .2s;
}
.icon-btn:hover:not(:disabled) { background: var(--glass-hover); color: var(--text-main); }
.icon-btn:disabled { opacity: .4; cursor: not-allowed; }
.peer-avatar {
  width: 40px; height: 40px; flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--grad-brand);
  padding: 2px;
  box-shadow: 0 3px 12px rgba(16, 185, 129, 0.35);
}
.peer-avatar .avatar-img { border-radius: 10px; }
.peer-info { min-width: 0; }
.peer-name { font-size: 15.5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.peer-status { font-size: 11px; color: var(--text-sub); margin-top: 2px; display: flex; align-items: center; gap: 5px; }
.peer-status i { font-size: 8px; color: var(--danger); }
.peer-status i.online { color: var(--accent-2); }
.top-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.model-chip i { color: var(--accent); }

/* ---------- 主体（会话栏 + 消息区） ---------- */
.chat-body { flex: 1; min-height: 0; display: flex; }

.session-panel {
  width: 224px; flex-shrink: 0;
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  background: var(--glass);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.session-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 8px;
  font-size: 12.5px; color: var(--text-sub);
  letter-spacing: .5px;
}
.session-count { color: var(--text-dim); font-size: 11px; }
.session-list { flex: 1; overflow-y: auto; padding: 4px 10px 12px; display: flex; flex-direction: column; gap: 3px; }
.session-item {
  display: flex; align-items: center; gap: 9px;
  width: 100%; text-align: left;
  padding: 9px 10px;
  border-radius: 11px;
  border: 1px solid transparent;
  transition: all .18s;
}
.session-item:hover { background: var(--glass-strong); }
.session-item.active {
  background: var(--grad-brand-soft);
  border-color: rgba(16, 185, 129, 0.35);
}
.sess-icon { color: var(--accent-2); font-size: 14px; flex-shrink: 0; }
.sess-info { flex: 1; min-width: 0; }
.sess-title {
  font-size: 12.5px; color: var(--text-main);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sess-meta { font-size: 10.5px; color: var(--text-dim); margin-top: 2px; }
.sess-del {
  opacity: 0; flex-shrink: 0;
  color: var(--text-dim); font-size: 12px;
  padding: 4px; border-radius: 6px;
  transition: all .18s;
  background: none; border: none; cursor: pointer;
}
.session-item:hover .sess-del { opacity: 1; }
.sess-del:hover { color: var(--danger); background: rgba(248, 113, 113, 0.12); }
.session-empty { text-align: center; padding: 36px 10px; font-size: 12px; color: var(--text-dim); line-height: 1.9; }

/* ---------- 消息区 ---------- */
.chat-scroll {
  flex: 1; overflow-y: auto;
  padding: 20px 22px;
  display: flex; flex-direction: column;
  scroll-behavior: smooth;
  min-width: 0;
}
.msg-list {
  display: flex; flex-direction: column; gap: 14px;
  width: 100%; max-width: 820px; margin: 0 auto;
}

/* ---------- 欢迎卡片 ---------- */
.welcome {
  margin: auto; width: min(560px, 100%); text-align: center;
  padding: 26px 20px;
}
.welcome-logo {
  width: 84px; height: 84px;
  margin: 0 auto 16px;
  border-radius: 24px;
  overflow: hidden;
  background: var(--grad-brand);
  padding: 3px;
  box-shadow: 0 10px 30px rgba(16, 185, 129, 0.4), var(--glow-accent);
  animation: floaty 3.6s ease-in-out infinite;
}
.welcome-logo .avatar-img { border-radius: 21px; }
.welcome-title {
  font-size: 22px; font-weight: 700;
  margin-bottom: 8px;
  background: var(--grad-text);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gradient-x 6s ease infinite;
}
.welcome-desc { color: var(--text-sub); font-size: 13px; line-height: 1.75; margin-bottom: 22px; }
.welcome-desc b { color: var(--accent); }
.welcome-cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.wc-card {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 13px;
  background: var(--glass-strong);
  border: 1px solid var(--border);
  border-radius: 12px;
  font-size: 13px; color: var(--text-main);
  cursor: pointer; text-align: left;
  transition: all .2s ease;
}
.wc-card i { color: var(--accent); font-size: 14px; }
.wc-card:hover {
  transform: translateY(-2px);
  background: var(--glass-hover);
  border-color: rgba(16,185,129,.45);
  box-shadow: 0 6px 18px rgba(16,185,129,.15);
}

/* ---------- 输入区 ---------- */
.chat-input-area {
  flex-shrink: 0;
  padding: 10px 16px 12px;
  background: var(--glass);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-top: 1px solid var(--border);
}
.input-tools { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.tool-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 11px; font-size: 12px;
  background: var(--glass-strong); border: 1px solid var(--border);
  color: var(--text-sub); border-radius: 999px;
  transition: all .2s;
}
.tool-btn.active { color: var(--accent); border-color: rgba(16,185,129,.45); background: rgba(16,185,129,.1); }
.tool-btn:hover { color: var(--text-main); }
.char-count { margin-left: auto; font-size: 11.5px; color: var(--text-dim); }
.char-count.over { color: var(--danger); }

.input-wrap {
  display: flex; align-items: flex-end; gap: 10px;
  background: var(--glass-strong);
  border: 1px solid var(--border-strong);
  border-radius: 22px;
  padding: 7px 7px 7px 16px;
  transition: border-color .2s, box-shadow .2s;
}
.input-wrap:focus-within {
  border-color: rgba(16,185,129,.5);
  box-shadow: 0 0 0 3px rgba(16,185,129,.12);
}
textarea {
  flex: 1; background: transparent; border: 0; outline: none;
  font-size: 15px; line-height: 1.6; max-height: 150px;
  resize: none; color: var(--text-main);
}
textarea::placeholder { color: var(--text-dim); }
.send-btn {
  width: 42px; height: 42px; flex-shrink: 0;
  display: grid; place-items: center;
  border-radius: 50%;
  background: var(--bubble-user-bg);
  color: var(--bubble-user-text);
  font-size: 16px;
  box-shadow: 0 4px 14px rgba(7, 193, 96, 0.35);
  transition: all .2s;
}
.send-btn:hover:not(:disabled) { transform: scale(1.06); box-shadow: 0 6px 20px rgba(7, 193, 96, 0.5); }
.send-btn:disabled { opacity: .45; cursor: not-allowed; transform: none; }
.input-hint { text-align: center; margin-top: 7px; font-size: 11px; color: var(--text-dim); }

@media (max-width: 820px) {
  .session-panel { position: absolute; left: 10px; top: 64px; bottom: 90px; z-index: 20; border-radius: 14px; box-shadow: var(--shadow); }
  .chat-body { position: relative; }
  .chat-scroll { padding: 14px 12px; }
  .chat-input-area { padding: 9px 10px 10px; }
  .model-chip { display: none; }
}
</style>
