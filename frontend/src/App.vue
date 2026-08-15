<template>
  <div class="app-shell">
    <AnimatedBackground />

    <div class="layout">
      <!-- ===== 左侧导航 ===== -->
      <aside class="sidebar" :class="{ collapsed }">
        <div class="brand" @click="$router.push('/')">
          <div class="brand-logo">
            <img src="@/assets/bot-avatar.png" alt="机器人" class="avatar-img" />
          </div>
          <div class="brand-text" v-show="!collapsed">
            <h1>Drink RAG</h1>
            <span>饮料健康智能问答</span>
          </div>
        </div>

        <nav class="nav">
          <router-link
            v-for="r in routes"
            :key="r.path"
            :to="r.path"
            class="nav-item"
            :title="r.meta.title"
          >
            <i :class="r.meta.icon"></i>
            <span v-show="!collapsed">{{ r.meta.title }}</span>
          </router-link>
        </nav>

        <div class="sidebar-foot">
          <div class="user-box" :title="isDark ? '切换浅色' : '切换深色'">
            <div class="user-avatar">
              <img src="@/assets/user-avatar.png" alt="我" class="avatar-img" />
            </div>
            <div class="user-meta" v-show="!collapsed">
              <span class="user-name">我</span>
              <span class="conn" :class="{ online: system.online }">
                <i class="fa-solid fa-circle"></i>{{ system.online ? '在线' : '离线' }}
              </span>
            </div>
          </div>
          <div class="foot-btns">
            <button class="icon-btn" @click="toggleTheme" :title="isDark ? '切换浅色' : '切换深色'">
              <i :class="isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon'"></i>
            </button>
            <button class="icon-btn" @click="collapsed = !collapsed" title="收起/展开侧栏">
              <i :class="collapsed ? 'fa-solid fa-angles-right' : 'fa-solid fa-angles-left'"></i>
            </button>
          </div>
        </div>
      </aside>

      <!-- ===== 主内容 ===== -->
      <main class="main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AnimatedBackground from '@/components/AnimatedBackground.vue'
import { useSystemStore } from '@/stores/system'

const router = useRouter()
const routes = router.getRoutes().filter((r) => r.meta?.title)
const system = useSystemStore()
const collapsed = ref(false)

const isDark = computed(() => document.documentElement.getAttribute('data-theme') !== 'light')

function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  localStorage.setItem('drink_theme', next)
}

onMounted(() => {
  system.load()
})
</script>

<style scoped>
.app-shell { position: relative; z-index: 1; height: 100vh; display: flex; }
.layout { flex: 1; display: flex; min-width: 0; gap: 16px; padding: 16px; }

/* ---------- 侧栏 ---------- */
.sidebar {
  width: 232px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--glass);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--shadow), var(--surface-inset);
  padding: 18px 14px;
  transition: width 0.3s ease;
  overflow: hidden;
}
.sidebar.collapsed { width: 72px; padding: 18px 12px; }

.brand { display: flex; align-items: center; gap: 12px; padding: 4px 6px 18px; cursor: pointer; }
.brand-logo {
  width: 48px; height: 48px; flex-shrink: 0;
  overflow: hidden;
  border-radius: 15px;
  padding: 2px;
  background: var(--grad-brand);
  box-shadow: 0 6px 18px rgba(14, 165, 233, 0.4), var(--glow-accent);
  animation: floaty 4s ease-in-out infinite;
}
.brand-logo .avatar-img { border-radius: 13px; }
.brand-text h1 { font-size: 18px; font-weight: 700; letter-spacing: .3px; }
.brand-text span { font-size: 11.5px; color: var(--text-sub); }

.nav { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  color: var(--text-sub);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.22s ease;
  border: 1px solid transparent;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}
.nav-item i { width: 18px; text-align: center; font-size: 15px; position: relative; z-index: 1; }
.nav-item span { position: relative; z-index: 1; }
.nav-item::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(120deg, transparent 30%, rgba(56,189,248,.10) 50%, transparent 70%);
  background-size: 250% 100%;
  opacity: 0;
  transition: opacity .3s;
}
.nav-item:hover { background: var(--glass-strong); color: var(--text-main); }
.nav-item:hover::after { opacity: 1; animation: shimmer 1.6s linear infinite; }
.nav-item.router-link-active {
  background: var(--grad-brand-soft);
  border-color: rgba(56, 189, 248, 0.35);
  color: var(--accent);
}

.sidebar-foot {
  margin-top: auto;
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}
.user-box {
  display: flex; align-items: center; gap: 10px;
  min-width: 0;
  cursor: pointer;
  padding: 4px;
  border-radius: 12px;
  transition: background .2s;
}
.user-box:hover { background: var(--glass-strong); }
.user-avatar {
  width: 34px; height: 34px; flex-shrink: 0;
  border-radius: 10px;
  overflow: hidden;
  padding: 2px;
  background: linear-gradient(135deg, #34d399, #0d9488);
  box-shadow: 0 3px 10px rgba(16, 185, 129, 0.3);
}
.user-avatar .avatar-img { border-radius: 8px; }
.user-meta { display: flex; flex-direction: column; min-width: 0; }
.user-name { font-size: 13px; font-weight: 600; }
.conn { display: flex; align-items: center; gap: 5px; font-size: 10.5px; color: var(--text-dim); }
.conn i { font-size: 7px; color: var(--danger); }
.conn.online i { color: var(--accent-2); }
.foot-btns { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.icon-btn {
  width: 32px; height: 32px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 10px;
  background: var(--glass-strong);
  border: 1px solid var(--border);
  color: var(--text-sub);
  font-size: 13px;
  transition: all 0.2s;
}
.icon-btn:hover { background: var(--glass-hover); color: var(--text-main); }

/* ---------- 主区 ---------- */
.main { flex: 1; min-width: 0; display: flex; }

@media (max-width: 820px) {
  .sidebar { width: 68px; padding: 18px 12px; }
  .sidebar .brand-text, .sidebar .nav-item span, .sidebar .conn span { display: none; }
  .layout { padding: 10px; gap: 10px; }
}
</style>
