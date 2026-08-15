<template>
  <div class="dv">
    <!-- ===== 顶栏 ===== -->
    <header class="dv-top">
      <div>
        <h2>系统监控</h2>
        <p class="sub">RAG 管道状态 · 运行指标 · 模型配置</p>
      </div>
      <button class="btn btn-ghost" @click="refresh" :disabled="loading">
        <i class="fa-solid" :class="loading ? 'fa-circle-notch fa-spin' : 'fa-rotate'"></i> 刷新
      </button>
    </header>

    <!-- ===== 状态卡片 ===== -->
    <div class="status-grid">
      <div class="s-card" :class="{ ok: st?.engine_ready }">
        <i class="fa-solid fa-gears"></i>
        <div><b>{{ st?.engine_ready ? '运行中' : '未就绪' }}</b><span>RAG 引擎</span></div>
      </div>
      <div class="s-card" :class="{ ok: st?.api_key_configured }">
        <i class="fa-solid fa-key"></i>
        <div><b>{{ st?.api_key_configured ? '已配置' : '未配置' }}</b><span>API Key</span></div>
      </div>
      <div class="s-card ok">
        <i class="fa-solid fa-clock-rotate-left"></i>
        <div><b>{{ formatUptime(st?.uptime_seconds) }}</b><span>运行时长</span></div>
      </div>
      <div class="s-card">
        <i class="fa-solid fa-microchip"></i>
        <div><b>{{ st?.device || 'cpu' }}</b><span>推理设备</span></div>
      </div>
    </div>

    <!-- ===== 指标卡片 ===== -->
    <div class="metric-grid">
      <div class="m-card"><span>文档数</span><b>{{ st?.doc_count ?? 0 }}</b><i class="fa-solid fa-file-lines" style="color:#38bdf8"></i></div>
      <div class="m-card"><span>知识分块</span><b>{{ st?.chunk_count ?? 0 }}</b><i class="fa-solid fa-cubes" style="color:#34d399"></i></div>
      <div class="m-card"><span>向量条数</span><b>{{ st?.vector_size ?? 0 }}</b><i class="fa-solid fa-database" style="color:#8b5cf6"></i></div>
      <div class="m-card"><span>今日问答</span><b>{{ st?.daily_qa ?? 0 }}</b><i class="fa-solid fa-comments" style="color:#fbbf24"></i></div>
      <div class="m-card"><span>会话数</span><b>{{ st?.conversation_count ?? 0 }}</b><i class="fa-solid fa-users" style="color:#f472b6"></i></div>
      <div class="m-card"><span>近30天问答</span><b>{{ st?.chat?.total_qa ?? 0 }}</b><i class="fa-solid fa-chart-column" style="color:#fb923c"></i></div>
    </div>

    <!-- ===== 图表区 ===== -->
    <div class="charts-row">
      <div class="chart-card">
        <h4><i class="fa-solid fa-chart-area"></i> 近 14 天问答趋势</h4>
        <div ref="qaChart" class="chart"></div>
      </div>
      <div class="chart-card">
        <h4><i class="fa-solid fa-pie-chart"></i> 知识分类分布</h4>
        <div ref="catChart" class="chart"></div>
      </div>
    </div>

    <!-- ===== RAG 管道配置 ===== -->
    <div class="panel">
      <h4 class="panel-title"><i class="fa-solid fa-sliders"></i> RAG 管道配置</h4>
      <div class="rag-grid">
        <div v-for="item in ragItems" :key="item.k" class="rag-item">
          <span>{{ item.label }}</span>
          <b>{{ item.v }}</b>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { useSystemStore } from '@/stores/system'
import { formatUptime } from '@/utils/format'

const sys = useSystemStore()
const loading = ref(false)
const qaChart = ref(null)
const catChart = ref(null)
let qaInst = null, catInst = null

const st = computed(() => sys.status)

const ragItems = computed(() => {
  const r = st.value?.rag || {}
  return [
    { k: 'top_k', label: '最终返回条数', v: r.top_k },
    { k: 'recall', label: '粗召回条数', v: r.retrieve_k },
    { k: 'rerank', label: '重排候选', v: r.rerank_k },
    { k: 'reranker', label: '交叉编码器重排', v: r.use_reranker ? '启用' : '关闭' },
    { k: 'fusion', label: '融合算法', v: r.use_rrf ? 'RRF' : '加权融合' },
    { k: 'chunk', label: '分块大小/重叠', v: `${r.chunk_size}/${r.chunk_overlap}` },
    { k: 'embed', label: '嵌入模型', v: r.embed_model?.split('/').pop() },
    { k: 'rerankModel', label: '重排模型', v: r.rerank_model?.split('/').pop() },
    { k: 'threshold', label: '相似度阈值', v: r.threshold },
    { k: 'rewrite', label: '查询改写', v: r.query_rewrite ? '启用' : '关闭' }
  ]
})

function renderCharts() {
  const theme = document.documentElement.getAttribute('data-theme')
  const axisColor = theme === 'light' ? '#8aa0bc' : '#64748b'
  const lineColor = theme === 'light' ? '#1e293b' : '#eef3fb'

  // 问答趋势
  if (qaInst) qaInst.dispose()
  qaInst = echarts.init(qaChart.value)
  qaInst.setOption({
    grid: { left: 12, right: 14, top: 26, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: sys.daily.map((d) => d.day.slice(5)),
      axisLine: { lineStyle: { color: axisColor } },
      axisLabel: { color: axisColor, fontSize: 11 }
    },
    yAxis: { type: 'value', axisLabel: { color: axisColor }, splitLine: { lineStyle: { color: 'rgba(128,140,170,.15)' } } },
    series: [
      {
        name: '问答数',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        data: sys.daily.map((d) => d.qa_count),
        lineStyle: { width: 3, color: '#38bdf8' },
        itemStyle: { color: '#38bdf8', borderColor: '#0ea5e9', borderWidth: 1 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: 'rgba(56,189,248,.35)' }, { offset: 1, color: 'rgba(56,189,248,0)' }] } }
      },
      {
        name: '文档上传',
        type: 'bar',
        data: sys.daily.map((d) => d.doc_uploads),
        itemStyle: { color: '#34d399', borderRadius: [4, 4, 0, 0] },
        barWidth: 14
      }
    ],
    legend: { textStyle: { color: lineColor }, top: 0 }
  })

  // 分类分布
  if (catInst) catInst.dispose()
  catInst = echarts.init(catChart.value)
  const cats = st.value ? uniqueCategories() : []
  catInst.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['38%', '68%'],
      center: ['50%', '54%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 8, borderColor: 'transparent', borderWidth: 2 },
      label: { color: lineColor, fontSize: 11, formatter: '{b}\n{d}%' },
      data: cats
    }]
  })
}

function uniqueCategories() {
  const map = {}
  for (const c of st.value?.knowledge?.categories || []) {
    map[c.category] = c.doc_count
  }
  return Object.entries(map).map(([name, value]) => ({ name, value }))
}

async function refresh() {
  loading.value = true
  await sys.load()
  await nextTick()
  renderCharts()
  loading.value = false
}

onMounted(async () => {
  await sys.load()
  await nextTick()
  renderCharts()
  window.addEventListener('resize', onResize)
})

function onResize() {
  qaInst?.resize()
  catInst?.resize()
}

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  qaInst?.dispose()
  catInst?.dispose()
})
</script>

<style scoped>
.dv { flex: 1; min-width: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; padding-right: 2px; }
.dv-top { display: flex; align-items: center; justify-content: space-between; }
.dv-top h2 { font-size: 19px; font-weight: 700; }
.sub { font-size: 12.5px; color: var(--text-sub); margin-top: 4px; }

/* 状态卡片 */
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.s-card {
  display: flex; align-items: center; gap: 14px;
  padding: 18px; border-radius: var(--radius);
  background: var(--glass); border: 1px solid var(--border);
  backdrop-filter: blur(14px); box-shadow: var(--shadow-soft);
}
.s-card > i { font-size: 24px; color: var(--warn); }
.s-card.ok > i { color: var(--accent-2); }
.s-card b { font-size: 17px; display: block; }
.s-card span { font-size: 12px; color: var(--text-sub); }

/* 指标卡片 */
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.m-card {
  position: relative; padding: 16px 18px;
  background: var(--glass); border: 1px solid var(--border);
  border-radius: var(--radius); backdrop-filter: blur(14px);
  box-shadow: var(--shadow-soft); overflow: hidden;
}
.m-card span { font-size: 12px; color: var(--text-sub); }
.m-card b { font-size: 25px; font-weight: 700; display: block; margin-top: 4px; }
.m-card > i { position: absolute; right: 16px; bottom: 14px; font-size: 30px; opacity: .25; }

/* 图表 */
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart-card {
  background: var(--glass); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px;
  backdrop-filter: blur(14px); box-shadow: var(--shadow-soft);
}
.chart-card h4 { font-size: 13.5px; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.chart-card h4 i { color: var(--accent); }
.chart { height: 240px; }

.panel {
  background: var(--glass); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 18px;
  backdrop-filter: blur(14px); box-shadow: var(--shadow-soft);
}
.panel-title { font-size: 14px; display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.panel-title i { color: var(--accent); }
.rag-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.rag-item {
  display: flex; flex-direction: column; gap: 4px;
  padding: 12px 14px;
  background: var(--glass-strong); border: 1px solid var(--border);
  border-radius: 12px;
}
.rag-item span { font-size: 11.5px; color: var(--text-sub); }
.rag-item b { font-size: 13px; word-break: break-all; }

@media (max-width: 900px) {
  .charts-row { grid-template-columns: 1fr; }
}
</style>
