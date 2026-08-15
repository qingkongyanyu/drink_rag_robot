<template>
  <div class="kv">
    <!-- ===== 顶栏 ===== -->
    <header class="kv-top">
      <div>
        <h2>知识库管理</h2>
        <p class="sub">上传、管理、检索您的知识文档 · 支持 txt / md / csv / json / pdf / docx</p>
      </div>
      <div class="kv-actions">
        <button class="btn btn-ghost" @click="tab = 'search'" :class="{ 'active-tab': tab === 'search' }">
          <i class="fa-solid fa-magnifying-glass"></i> 检索调试
        </button>
        <button class="btn btn-primary" @click="openUpload">
          <i class="fa-solid fa-cloud-arrow-up"></i> 上传知识
        </button>
      </div>
    </header>

    <!-- ===== 统计卡片 ===== -->
    <div class="stat-row">
      <div class="stat-card"><i class="fa-solid fa-file-lines c1"></i><b>{{ kb.totalDocs }}</b><span>文档数</span></div>
      <div class="stat-card"><i class="fa-solid fa-cubes c2"></i><b>{{ kb.totalChunks }}</b><span>知识分块</span></div>
      <div class="stat-card"><i class="fa-solid fa-shapes c3"></i><b>{{ categoryCount }}</b><span>分类数</span></div>
      <div class="stat-card"><i class="fa-solid fa-database c4"></i><b>{{ stats?.vector_dim ?? '—' }}</b><span>向量维度</span></div>
    </div>

    <!-- ===== 检索调试 Tab ===== -->
    <section v-if="tab === 'search'" class="panel search-panel">
      <div class="search-bar">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input v-model="searchQuery" placeholder="输入查询，测试 RAG 检索质量（混合召回 + 重排）…" @keyup.enter="doSearch" />
        <button class="btn btn-primary btn-sm" :disabled="!searchQuery || searching" @click="doSearch">
          <i class="fa-solid" :class="searching ? 'fa-circle-notch fa-spin' : 'fa-play'"></i>
        </button>
      </div>
      <div v-if="searchResult" class="search-result">
        <div class="sr-head">
          <span>命中 {{ searchResult.results.length }} 条 · 耗时 {{ searchResult.elapsed_ms }}ms</span>
          <span class="sr-tip">方法：<em>混合召回</em>=语义+关键词</span>
        </div>
        <div v-if="!searchResult.results.length" class="sr-empty">未检索到相关内容，试试更换关键词或上传更多知识。</div>
        <div v-for="(r, i) in searchResult.results" :key="i" class="sr-item">
          <div class="sr-rank">{{ i + 1 }}</div>
          <div class="sr-body">
            <div class="sr-title">
              {{ r.filename }}
              <span class="method-badge" :class="r.method">{{ methodText(r.method) }}</span>
              <span class="score">score {{ r.score?.toFixed?.(3) }}</span>
            </div>
            <p class="sr-content">{{ r.content }}</p>
            <div class="sr-meta">
              <span class="tag">{{ r.category }}</span>
              <span class="tag">分块 {{ r.chunk_index }}</span>
              <span class="tag">doc#{{ r.doc_id }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 文档列表 Tab ===== -->
    <section v-else class="panel">
      <!-- 上传拖拽区 -->
      <div
        class="drop-zone"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput?.click()"
      >
        <input ref="fileInput" type="file" multiple :accept="ACCEPT" hidden @change="onPick" />
        <i class="fa-solid fa-cloud-arrow-up"></i>
        <div>
          <b>拖拽文件到此处，或点击选择</b>
          <p>支持 {{ ACCEPT.replaceAll('.', '') }} 格式 · 单文件 ≤ 20MB · 单次最多 10 个</p>
        </div>
        <div class="cat-picker" @click.stop>
          <label for="cat">分类</label>
          <input id="cat" v-model="category" placeholder="默认分类" maxlength="20" />
        </div>
        <button v-if="files.length" class="btn btn-primary btn-sm" @click.stop="doUpload" :disabled="kb.uploading">
          <i class="fa-solid" :class="kb.uploading ? 'fa-circle-notch fa-spin' : 'fa-upload'"></i>
          {{ kb.uploading ? '上传中…' : `上传 ${files.length} 个文件` }}
        </button>
      </div>

      <!-- 上传进度反馈 -->
      <div v-if="uploadResult" class="upload-result" :class="uploadResult.failed_count ? 'warn' : 'ok'">
        <i class="fa-solid" :class="uploadResult.failed_count ? 'fa-triangle-exclamation' : 'fa-circle-check'"></i>
        <span>成功 {{ uploadResult.success_count }} · 失败 {{ uploadResult.failed_count }}</span>
        <div v-if="uploadResult.failed?.length" class="upload-fails">
          <div v-for="(f, i) in uploadResult.failed" :key="i">{{ f.filename }}：{{ f.error }}</div>
        </div>
      </div>

      <!-- 文档卡片 -->
      <div v-if="!kb.docs.length" class="empty-state">
        <i class="fa-solid fa-folder-open"></i>
        <p>知识库为空，上传第一个文档开始构建</p>
      </div>
      <div v-else class="doc-grid">
        <div v-for="d in kb.docs" :key="d.id" class="doc-card">
          <div class="doc-head">
            <div class="doc-icon" :style="{ background: typeColor(d.file_type) + '22', color: typeColor(d.file_type) }">
              <i :class="typeIcon(d.file_type)"></i>
            </div>
            <div class="doc-name">
              <h4 :title="d.filename">{{ d.filename }}</h4>
              <span class="doc-meta">{{ d.file_type.toUpperCase() }} · {{ formatSize(d.size) }}</span>
            </div>
            <span class="doc-status" :class="d.status">{{ statusText(d.status) }}</span>
          </div>
          <div class="doc-body">
            <span class="doc-cat"><i class="fa-solid fa-tag"></i>{{ d.category }}</span>
            <span class="doc-cat"><i class="fa-solid fa-layer-group"></i>{{ d.chunk_count }} 块</span>
            <span class="doc-cat"><i class="fa-regular fa-clock"></i>{{ formatClock(d.created_at * 1000) }}</span>
          </div>
          <div v-if="d.error" class="doc-error">{{ d.error }}</div>
          <div class="doc-actions">
            <button class="btn btn-ghost btn-sm" @click="preview(d)">
              <i class="fa-regular fa-eye"></i> 查看
            </button>
            <button class="btn btn-ghost btn-danger-ghost btn-sm" @click="remove(d)">
              <i class="fa-regular fa-trash-can"></i> 删除
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== 文档详情抽屉 ===== -->
    <div v-if="previewDoc" class="drawer-mask" @click.self="previewDoc = null">
      <div class="drawer">
        <header class="drawer-head">
          <div>
            <h3>{{ previewDoc.filename }}</h3>
            <p>{{ previewDoc.file_type.toUpperCase() }} · {{ previewDoc.chunk_count }} 块 · {{ formatSize(previewDoc.size) }}</p>
          </div>
          <button class="icon-x" @click="previewDoc = null"><i class="fa-solid fa-xmark"></i></button>
        </header>
        <div class="drawer-body">
          <div v-for="c in previewDoc.chunks" :key="c.id" class="chunk-row">
            <div class="chunk-idx">#{{ c.chunk_index }}</div>
            <div class="chunk-content">
              <pre>{{ c.content }}</pre>
              <span class="chunk-vec">vector_id: {{ c.vector_id ?? '—' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 隐藏文件选择 -->
    <input ref="hiddenInput" type="file" multiple :accept="ACCEPT" hidden @change="onPick" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { fetchDocDetail } from '@/api/knowledge'
import { searchKnowledge } from '@/api/knowledge'
import { formatClock, formatSize, typeColor } from '@/utils/format'

const kb = useKnowledgeStore()
const tab = ref('list')
const files = ref([])
const category = ref('')
const dragging = ref(false)
const fileInput = ref(null)
const hiddenInput = ref(null)
const uploadResult = ref(null)
const ACCEPT = '.txt,.md,.csv,.json,.pdf,.docx'
const previewDoc = ref(null)

const searchQuery = ref('')
const searching = ref(false)
const searchResult = ref(null)

const categoryCount = computed(() => {
  const set = new Set(kb.docs.map((d) => d.category))
  return set.size
})
const stats = computed(() => kb.stats)

onMounted(() => kb.load())

function openUpload() { fileInput.value?.click() }
function onPick(e) {
  files.value = Array.from(e.target.files || [])
  if (e.target === hiddenInput.value) { /* keep for reset */ }
  e.target.value = ''
}
function onDrop(e) {
  dragging.value = false
  files.value = Array.from(e.dataTransfer?.files || [])
}
async function doUpload() {
  if (!files.value.length || kb.uploading) return
  try {
    uploadResult.value = await kb.upload(files.value, category.value || '默认分类')
    files.value = []
  } catch (err) {
    uploadResult.value = { success_count: 0, failed_count: 1, failed: [{ filename: '上传', error: err.message }] }
  }
}

function statusText(s) {
  return { ready: '已就绪', processing: '处理中', failed: '失败' }[s] || s
}
function typeIcon(t) {
  return { txt: 'fa-solid fa-file-lines', md: 'fa-brands fa-markdown', csv: 'fa-solid fa-table',
           json: 'fa-solid fa-braces', pdf: 'fa-solid fa-file-pdf', docx: 'fa-solid fa-file-word',
           builtin: 'fa-solid fa-book-bookmark' }[t] || 'fa-solid fa-file'
}
function methodText(m) {
  return { hybrid: '混合', dense: '语义', sparse: '关键词' }[m] || m
}

async function remove(d) {
  if (!confirm(`确定删除「${d.filename}」及其 ${d.chunk_count} 个知识块？`)) return
  await kb.remove(d.id)
}
async function preview(d) {
  const res = await fetchDocDetail(d.id)
  previewDoc.value = res.data
}
async function doSearch() {
  if (!searchQuery.value || searching.value) return
  searching.value = true
  try {
    const res = await searchKnowledge(searchQuery.value, 8)
    searchResult.value = res.data
  } finally {
    searching.value = false
  }
}
</script>

<style scoped>
.kv { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; overflow: hidden; }

.kv-top { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.kv-top h2 { font-size: 19px; font-weight: 700; }
.sub { font-size: 12.5px; color: var(--text-sub); margin-top: 4px; }
.kv-actions { display: flex; gap: 10px; }
.active-tab { color: var(--accent) !important; border-color: rgba(56,189,248,.5) !important; }

/* 统计卡片 */
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.stat-card {
  display: flex; flex-direction: column; gap: 6px;
  padding: 18px;
  background: var(--glass); border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(14px);
  box-shadow: var(--shadow-soft);
}
.stat-card i { font-size: 20px; }
.stat-card b { font-size: 26px; font-weight: 700; }
.stat-card span { font-size: 12px; color: var(--text-sub); }
.c1 { color: #38bdf8; } .c2 { color: #34d399; } .c3 { color: #8b5cf6; } .c4 { color: #fbbf24; }

.panel {
  flex: 1; overflow-y: auto;
  background: var(--glass); border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(14px);
  box-shadow: var(--shadow);
  padding: 20px;
}

/* 拖拽上传 */
.drop-zone {
  display: flex; align-items: center; gap: 18px;
  padding: 24px;
  border: 2px dashed var(--border-strong);
  border-radius: var(--radius);
  cursor: pointer;
  transition: all .25s;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.drop-zone:hover, .drop-zone.dragging { border-color: var(--accent); background: rgba(56,189,248,.06); }
.drop-zone > i { font-size: 34px; color: var(--accent); }
.drop-zone b { font-size: 14.5px; }
.drop-zone p { font-size: 12px; color: var(--text-sub); margin-top: 4px; }
.cat-picker { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.cat-picker label { font-size: 12.5px; color: var(--text-sub); }
.cat-picker input {
  width: 120px; padding: 7px 12px; font-size: 13px;
  background: var(--glass-strong); border: 1px solid var(--border);
  border-radius: 10px;
}

.upload-result {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 12px 16px; border-radius: 12px; margin-bottom: 16px; font-size: 13px;
}
.upload-result.ok { background: rgba(52,211,153,.1); border: 1px solid rgba(52,211,153,.3); color: var(--accent-2); }
.upload-result.warn { background: rgba(251,191,36,.1); border: 1px solid rgba(251,191,36,.3); color: var(--warn); }
.upload-fails { width: 100%; font-size: 12px; color: var(--danger); }

/* 文档卡片 */
.doc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.doc-card {
  background: var(--glass-strong); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px;
  transition: all .22s;
  display: flex; flex-direction: column; gap: 12px;
}
.doc-card:hover { transform: translateY(-3px); border-color: var(--border-strong); box-shadow: var(--shadow); }
.doc-head { display: flex; align-items: center; gap: 12px; }
.doc-icon {
  width: 42px; height: 42px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px; font-size: 17px;
}
.doc-name { flex: 1; min-width: 0; }
.doc-name h4 { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doc-meta { font-size: 11.5px; color: var(--text-dim); }
.doc-status { font-size: 11px; padding: 2px 9px; border-radius: 999px; }
.doc-status.ready { color: var(--accent-2); background: rgba(52,211,153,.1); }
.doc-status.processing { color: var(--warn); background: rgba(251,191,36,.1); }
.doc-status.failed { color: var(--danger); background: rgba(248,113,113,.1); }
.doc-body { display: flex; gap: 10px; flex-wrap: wrap; }
.doc-cat { font-size: 11.5px; color: var(--text-sub); display: inline-flex; align-items: center; gap: 5px; }
.doc-error { font-size: 11.5px; color: var(--danger); background: rgba(248,113,113,.08); padding: 7px 10px; border-radius: 8px; }
.doc-actions { display: flex; gap: 8px; margin-top: auto; }

.empty-state { text-align: center; padding: 60px 0; color: var(--text-dim); }
.empty-state i { font-size: 46px; margin-bottom: 14px; opacity: .5; }

/* 检索面板 */
.search-panel { display: flex; flex-direction: column; }
.search-bar {
  display: flex; align-items: center; gap: 10px;
  background: var(--glass-strong); border: 1px solid var(--border-strong);
  border-radius: 14px; padding: 10px 14px;
}
.search-bar i { color: var(--text-dim); }
.search-bar input { flex: 1; background: transparent; font-size: 14px; }
.search-result { margin-top: 18px; display: flex; flex-direction: column; gap: 10px; }
.sr-head { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--text-sub); }
.sr-tip em { color: var(--accent); font-style: normal; }
.sr-empty { text-align: center; padding: 30px; color: var(--text-dim); }
.sr-item { display: flex; gap: 12px; background: var(--glass-strong); border: 1px solid var(--border); border-radius: 12px; padding: 13px 15px; }
.sr-rank {
  width: 26px; height: 26px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff;
  background: var(--grad-brand); border-radius: 8px;
}
.sr-body { flex: 1; min-width: 0; }
.sr-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sr-content { font-size: 12.5px; color: var(--text-sub); margin-top: 5px; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.method-badge { font-size: 10.5px; padding: 1px 8px; border-radius: 999px; }
.method-badge.hybrid { color: #8b5cf6; background: rgba(139,92,246,.12); }
.method-badge.dense { color: #38bdf8; background: rgba(56,189,248,.12); }
.method-badge.sparse { color: #f59e0b; background: rgba(245,158,11,.12); }
.score { font-size: 11px; color: var(--accent-2); }
.sr-meta { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
.tag { font-size: 10.5px; color: var(--text-dim); background: var(--glass-strong); padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border); }

/* 抽屉 */
.drawer-mask { position: fixed; inset: 0; z-index: 100; background: rgba(0,0,0,.5); backdrop-filter: blur(4px); display: flex; justify-content: flex-end; animation: fadeIn .2s; }
.drawer {
  width: min(620px, 92vw); height: 100%;
  background: var(--bg-1); border-left: 1px solid var(--border);
  box-shadow: -20px 0 60px rgba(0,0,0,.4);
  display: flex; flex-direction: column;
  animation: fadeInUp .28s ease;
}
.drawer-head { display: flex; align-items: center; justify-content: space-between; padding: 20px 22px; border-bottom: 1px solid var(--border); }
.drawer-head h3 { font-size: 16px; }
.drawer-head p { font-size: 12px; color: var(--text-sub); margin-top: 4px; }
.icon-x { width: 34px; height: 34px; border-radius: 10px; background: var(--glass-strong); border: 1px solid var(--border); color: var(--text-sub); }
.icon-x:hover { color: var(--danger); }
.drawer-body { flex: 1; overflow-y: auto; padding: 18px 22px; display: flex; flex-direction: column; gap: 10px; }
.chunk-row { display: flex; gap: 10px; }
.chunk-idx { font-size: 11px; font-weight: 700; color: var(--accent); flex-shrink: 0; padding-top: 3px; }
.chunk-content { flex: 1; background: var(--glass-strong); border: 1px solid var(--border); border-radius: 10px; padding: 10px 13px; }
.chunk-content pre { white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 12.5px; line-height: 1.6; color: var(--text-sub); }
.chunk-vec { display: inline-block; margin-top: 6px; font-size: 10.5px; color: var(--text-dim); }
</style>
