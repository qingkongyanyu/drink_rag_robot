import MarkdownIt from 'markdown-it'

// Markdown 渲染器（安全模式：禁用内联 HTML）
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false
})

// 增强代码块渲染，标注语言
const defaultFence = md.renderer.rules.fence || function (tokens, idx, options, env, self) {
  return self.renderToken(tokens, idx, options)
}
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const lang = token.info ? token.info.trim() : ''
  const code = token.content
  const langLabel = lang ? `<span class="code-lang">${lang}</span>` : ''
  const highlighted = lang
    ? `<pre class="code-block"><div class="code-head">${langLabel}<button class="code-copy" onclick="copyCode(this)">复制</button></div><code class="language-${lang}">${escapeHtml(code)}</code></pre>`
    : `<pre class="code-block"><div class="code-head"><span class="code-lang">text</span><button class="code-copy" onclick="copyCode(this)">复制</button></div><code>${escapeHtml(code)}</code></pre>`
  return highlighted
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

export function renderMarkdown(text) {
  return md.render(text || '')
}

// 供内联 onclick 使用
window.copyCode = (btn) => {
  const code = btn.closest('.code-block').querySelector('code')
  const text = code.textContent
  navigator.clipboard?.writeText(text).then(() => {
    btn.textContent = '已复制'
    setTimeout(() => (btn.textContent = '复制'), 1500)
  })
}
