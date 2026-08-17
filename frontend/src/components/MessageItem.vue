<template>
  <div class="msg" :class="role" :id="`msg-${msg.id}`">
    <!-- 头像：AI 在左，用户在右 -->
    <div class="avatar" :class="role">
      <img
        v-if="role === 'assistant'"
        src="@/assets/bot-avatar.png"
        alt="机器人"
        class="avatar-img"
      />
      <img v-else src="@/assets/user-avatar.png" alt="我" class="avatar-img" />
    </div>

    <div class="msg-main">
      <!-- 昵称 -->
      <div class="msg-name">{{ role === 'assistant' ? 'Drink 机器人' : '我' }}</div>

      <!-- 气泡 -->
      <div class="bubble-wrap">
        <div class="bubble" :class="role">
          <!-- 助手：Markdown 渲染 -->
          <div v-if="role === 'assistant'" class="md-body" v-html="html"></div>
          <!-- 用户：纯文本 -->
          <div v-else class="user-text">{{ msg.content }}</div>

          <!-- 打字指示 -->
          <div v-if="msg.streaming" class="typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>

        <!-- 气泡下工具条 -->
        <div v-if="role === 'assistant'" class="msg-actions">
          <span class="msg-time">{{ msg.time }}</span>
          <span v-if="msg.streaming" class="badge streaming-badge">生成中</span>
          <span v-else-if="msg.useKnowledge !== false && msg.sources?.length" class="badge">引用 {{ msg.sources.length }} 处</span>
          <span v-else-if="!msg.streaming && msg.sources?.length === 0" class="badge no-kb">未检索到知识</span>
          <span v-if="!msg.streaming && msg.latency != null" class="badge">{{ msg.latency }}ms</span>
          <button v-if="!msg.streaming && msg.content" class="copy-btn" @click="copy" title="复制回答">
            <i class="fa-regular fa-copy"></i>
          </button>
        </div>
        <div v-else class="msg-actions right">
          <span class="msg-time">{{ msg.time }}</span>
        </div>
      </div>

      <!-- 引用来源 -->
      <div v-if="msg.sources?.length && !msg.streaming" class="sources">
        <div class="sources-head" @click="showSources = !showSources">
          <i class="fa-solid fa-book-open"></i>
          <span>参考来源（{{ msg.sources.length }}）</span>
          <i class="fa-solid" :class="showSources ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
        </div>
        <transition name="fade">
          <div v-show="showSources" class="sources-list">
            <div v-for="(s, i) in msg.sources" :key="i" class="source-item">
              <span class="src-idx">{{ i + 1 }}</span>
              <div class="src-info">
                <div class="src-title">
                  {{ s.filename }}
                  <em class="src-method">{{ methodLabel(s.method) }}</em>
                </div>
                <p class="src-snippet">{{ s.snippet }}</p>
                <div class="src-tags">
                  <span class="src-tag">{{ s.category }}</span>
                  <span class="src-tag">分块 {{ s.chunk_index }}</span>
                  <span class="src-tag">相似度 {{ s.score?.toFixed?.(3) }}</span>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({ msg: { type: Object, required: true } })
const showSources = ref(false)

// 角色（user / assistant）之前模板里用了却没定义，导致所有消息都走 v-else 显示用户头像
const role = computed(() => props.msg.role || 'user')

const html = computed(() => renderMarkdown(props.msg.content || ''))

function methodLabel(m) {
  const map = { hybrid: '混合召回', dense: '语义召回', sparse: '关键词召回' }
  return map[m] || m || ''
}

async function copy() {
  try {
    await navigator.clipboard.writeText(props.msg.content)
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = props.msg.content
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
  }
}
</script>

<style scoped>
/* ===== 微信风消息行 ===== */
.msg {
  display: flex;
  gap: 10px;
  max-width: 86%;
  animation: fadeInUp 0.28s ease both;
}
.msg.user { flex-direction: row-reverse; align-self: flex-end; }
.msg.assistant { align-self: flex-start; }

/* ---------- 头像 ---------- */
.avatar {
  width: 40px; height: 40px; flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  margin-top: 18px; /* 对齐昵称行 */
}
.avatar .avatar-img { border-radius: 0; }

/* ---------- 主体 ---------- */
.msg-main { display: flex; flex-direction: column; min-width: 0; max-width: 100%; }
.msg.user .msg-main { align-items: flex-end; }

.msg-name {
  font-size: 11px;
  color: var(--text-dim);
  margin: 0 4px 3px;
}

/* ---------- 气泡 ---------- */
.bubble-wrap { display: flex; flex-direction: column; min-width: 0; max-width: 100%; }
.msg.user .bubble-wrap { align-items: flex-end; }

.bubble {
  position: relative;
  padding: 11px 15px;
  border-radius: 10px;
  font-size: 14.5px;
  line-height: 1.72;
  max-width: 100%;
  min-width: 0;
}

/* AI 气泡：浅色（左，尾巴右下） */
.msg.assistant .bubble {
  background: var(--bubble-ai-bg);
  border: 1px solid var(--bubble-ai-border);
  color: var(--bubble-ai-text);
  border-top-left-radius: 3px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}
.msg.assistant .bubble::before {
  content: '';
  position: absolute;
  left: -6px; top: 0;
  border: 7px solid transparent;
  border-top-color: var(--bubble-tail-ai);
  border-right-color: var(--bubble-tail-ai);
  border-left: 0;
}

/* 用户气泡：微信绿（右，尾巴左下） */
.msg.user .bubble {
  background: var(--bubble-user-bg);
  color: var(--bubble-user-text);
  border-top-right-radius: 3px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}
.msg.user .bubble::after {
  content: '';
  position: absolute;
  right: -6px; top: 0;
  border: 7px solid transparent;
  border-top-color: var(--bubble-tail-user);
  border-left-color: var(--bubble-tail-user);
  border-right: 0;
}

.user-text { white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }

/* ---------- 打字指示 ---------- */
.typing-dots { display: inline-flex; gap: 5px; margin-top: 3px; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent);
  animation: dotBounce 1.2s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: .18s; }
.typing-dots span:nth-child(3) { animation-delay: .36s; }
@keyframes dotBounce { 0%,60%,100% { transform: translateY(0); opacity:.5 } 30% { transform: translateY(-6px); opacity:1 } }

/* ---------- 工具条 ---------- */
.msg-actions {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 2px 0;
  flex-wrap: wrap;
}
.msg-actions.right { justify-content: flex-end; }
.msg-time { font-size: 11px; color: var(--text-dim); }
.badge {
  font-size: 11px; color: var(--text-sub);
  background: var(--glass-strong);
  padding: 2px 9px; border-radius: 999px;
  border: 1px solid var(--border);
}
.streaming-badge { color: var(--accent); border-color: rgba(56,189,248,.4); }
.no-kb { color: var(--warn); border-color: rgba(251,191,36,.35); }
.copy-btn {
  background: none; border: none; color: var(--text-dim);
  font-size: 12px; padding: 2px 6px; border-radius: 6px;
  transition: all .2s;
}
.copy-btn:hover { color: var(--accent); background: var(--glass-strong); }

/* ---------- 来源引用 ---------- */
.sources { margin-top: 7px; max-width: 100%; }
.sources-head {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--text-sub);
  cursor: pointer; padding: 5px 10px;
  background: var(--glass-strong); border: 1px solid var(--border);
  border-radius: 999px;
  transition: all .2s;
}
.sources-head:hover { color: var(--accent); border-color: rgba(56,189,248,.4); }
.sources-list {
  margin-top: 8px; display: flex; flex-direction: column; gap: 8px;
  padding: 12px; background: var(--glass); border: 1px solid var(--border);
  border-radius: 12px; max-width: 620px;
}
.source-item { display: flex; gap: 10px; min-width: 0; }
.src-idx {
  width: 22px; height: 22px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: #fff;
  background: var(--grad-brand); border-radius: 7px;
}
.src-title { font-size: 13px; font-weight: 600; color: var(--text-main); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.src-method { font-style: normal; font-size: 11px; color: var(--accent-2); background: rgba(52,211,153,.12); padding: 1px 7px; border-radius: 999px; }
.src-snippet {
  font-size: 12px; color: var(--text-sub); margin-top: 3px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  word-break: break-all;
}
.src-tags { display: flex; gap: 6px; margin-top: 5px; flex-wrap: wrap; }
.src-tag { font-size: 10.5px; color: var(--text-dim); background: var(--glass-strong); padding: 1px 7px; border-radius: 999px; border: 1px solid var(--border); }

@media (max-width: 760px) {
  .msg { max-width: 94%; }
  .avatar { width: 36px; height: 36px; }
}
</style>
