<div align="center">

# 🥤 Drink RAG Robot · 饮料健康知识问答

**基于「高级 RAG」与「千问大模型」的智能饮料健康问答平台**

FastAPI · Vue 3 · 混合检索 · 语义重排 · 流式输出 · 知识库管理

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D)
![RAG](https://img.shields.io/badge/RAG-Hybrid%20Retrieval-orange)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 📖 项目简介

面向「超市常见饮料健康知识」的专业问答系统。区别于简单的关键词检索，本项目实现了**完整的高质量 RAG 技术栈**：

- **语义向量检索**（`BAAI/bge-small-zh` 中文嵌入）与 **BM25 关键词检索**双路召回，**RRF 融合**；
- 可选**交叉编码器语义重排**（`bge-reranker-base`），显著提升排序精度；
- **多轮对话查询改写**（指代消解），让追问更准确；
- **知识库管理**：一键上传 `txt / md / csv / json / pdf / docx`，自动解析、分块、入库、检索；
- **SSE 流式输出** + **来源引用**，回答可溯源、可验证；
- 内置 **100 款饮料**结构化知识库，开箱即用。

## ✨ 核心特性

| 模块 | 能力 |
|------|------|
| 🎙 智能对话 | 流式打字机效果、Markdown 渲染、多轮上下文记忆、来源引用 |
| 🧠 高级 RAG | 混合检索（Dense+BM25）→ RRF 融合 → 交叉编码器重排 → 引用生成 |
| 📚 知识库 | 多格式上传、自动分块、在线搜索调试、文档管理 |
| 📊 系统监控 | 运行状态、向量库指标、问答趋势图表、RAG 管道配置可视化 |
| 🎨 前端体验 | Vue3 + Vite + Pinia、**微信风聊天气泡**（左AI/右用户）、深空玻璃拟态 + 极光动效、自定义头像、深/浅主题、完全响应式 |

## 🚀 快速开始

### 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.10+（本项目在 3.10.11 验证） |
| Node.js | 18+（构建前端，建议 20+） |
| GPU（可选） | 有 CUDA 的 NVIDIA 显卡可加速向量化 |
| 网络 | 需访问千问 DashScope API；模型下载走国内镜像 |

### 第一步：安装依赖

```bash
# 后端
pip install -r backend/requirements.txt

# 前端
cd frontend && npm install && cd ..
```

### 第二步：配置密钥

```bash
cp .env.example .env        # Windows: copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY（千问 DashScope 密钥）
```

> 密钥申请：https://dashscope.console.aliyun.com/ （阿里云百炼平台，新用户有免费额度）

### 第三步：启动

```bash
python start.py             # 一键启动（自动检测环境、构建前端、拉起服务）
```

或分步启动：

```bash
# 终端 A：构建前端（已构建可跳过）
cd frontend && npm run build && cd ..

# 终端 B：启动后端
uvicorn backend.main:app --host 0.0.0.0 --port 8006
```

### 访问

| 入口 | 地址 |
|------|------|
| 应用主页 | http://127.0.0.1:8006 |
| API 文档（Swagger） | http://127.0.0.1:8006/api/docs |
| API 文档（ReDoc） | http://127.0.0.1:8006/api/redoc |

> 💬 聊天界面为**微信风格**：机器人回答在左侧气泡，你的消息在右侧绿色气泡，头像自动区分（机器人使用 `imag/1.jpg`，用户使用 `imag/2.webp`）。

### 开发模式（前后端分离热更新）

```bash
# 终端 A：后端
uvicorn backend.main:app --reload --port 8006

# 终端 B：前端（Vite 代理 /api → 8006）
cd frontend && npm run dev        # http://localhost:5173
```

## 🧪 测试

```bash
# 单元测试（离线可跑）
python -m unittest backend.tests.test_rag -v

# API 冒烟测试（需先启动服务）
python scripts/test_api.py
```

## 🗂 文档索引

| 文档 | 说明 |
|------|------|
| [docs/技术栈.md](docs/技术栈.md) | 技术栈详解：每项技术的版本、职责、选型理由与备选对比 |
| [docs/架构设计.md](docs/架构设计.md) | 系统架构、模块划分、数据流、设计取舍 |
| [docs/RAG技术方案.md](docs/RAG技术方案.md) | 检索链路详解：嵌入/BM25/RRF/重排/改写 |
| [docs/项目结构书.md](docs/项目结构书.md) | 完整目录结构与职责说明 |
| [docs/API接口文档.md](docs/API接口文档.md) | 全部接口契约与示例 |
| [docs/部署运维指南.md](docs/部署运维指南.md) | 本地部署、服务器部署、运维监控 |
| [docs/测试报告.md](docs/测试报告.md) | 单元测试与接口测试结果 |
| [docs/面试要点.md](docs/面试要点.md) | 项目技术亮点与 Q&A |
| [docs/用户使用手册.md](docs/用户使用手册.md) | 面向使用者的操作手册 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 版本迭代记录 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南（开发 / 规范 / PR 流程） |
| [SECURITY.md](SECURITY.md) | 安全策略与漏洞报告 |

## 🏗 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · Uvicorn · pydantic v2 · **openai SDK**（千问兼容协议） |
| 嵌入/检索 | sentence-transformers（bge-small-zh）· FAISS · 自研 BM25（jieba+numpy） |
| 持久化 | SQLite（WAL） |
| 前端 | Vue 3 · Vite · Pinia · Vue Router · ECharts · Markdown-it |
| 文档解析 | pypdf · python-docx |

> 每项技术的**版本、职责、选型理由与备选对比**详见 [docs/技术栈.md](docs/技术栈.md)。

## 📁 目录结构（概览）

```
drink_rag_robot/
├── backend/            # FastAPI 后端
│   ├── main.py         # 应用入口（工厂模式）
│   ├── api/            # 路由层（chat / knowledge / system）
│   ├── core/           # 配置、数据库、日志
│   ├── models/         # Pydantic 数据模型
│   ├── rag/            # RAG 引擎（嵌入/向量库/BM25/混合/重排/分块/解析）
│   ├── services/       # 业务服务（LLM/对话/知识库/统计）
│   └── tests/          # 单元测试
├── frontend/           # Vue3 前端
├── imag/               # 头像图片（imag/1.jpg 机器人 · imag/2.webp 用户）
├── data/               # 内置知识库与运行时数据
├── docs/               # 全套文档
├── scripts/            # 运维脚本（API 测试等）
├── start.py            # 一键启动
└── .env.example        # 配置模板
```

## ⚠️ 常见问题

<details>
<summary><b>Q：流式回答“时好时坏”或不出字？</b></summary>

v3.1 已修复：此前后端 SSE 将事件类型放在 `event:` 行而前端只解析 `data:` 行，导致流式事件无法分发。
现在前端同时兼容两种 SSE 形态（`event:` 行与 `data.type`），后端也做了双写。若仍异常，请确认只启动了一个后端实例
（重复启动会抢占 8006 端口导致请求随机分发），并清理浏览器缓存后强刷（Ctrl+F5）。
</details>

<details>
<summary><b>Q：模型下载很慢或失败？</b></summary>

系统默认走国内镜像 `hf-mirror.com` 下载嵌入/重排模型（见 `backend/core/config.py`），
如网络受限，可配置代理或修改 `HF_ENDPOINT=https://huggingface.co`。
</details>

<details>
<summary><b>Q：开启语义重排？</b></summary>

重排模型 `bge-reranker-base` 约 800MB，首次需联网下载。
下载完成后在 `.env` 设置 `RAG_USE_RERANKER=true` 重启即可；未开启时自动降级为 RRF 融合排序。
</details>

<details>
<summary><b>Q：如何更换大模型？</b></summary>

`.env` 中 `LLM_MODEL` 支持 `qwen-turbo / qwen-plus / qwen-max`；
`LLM_BASE_URL` 使用 OpenAI 兼容基础地址（openai SDK 的 `base_url`），可整体替换为任意兼容服务商。
（旧版完整端点 `LLM_API_URL` 仍兼容，代码会自动去掉 `/chat/completions` 后缀。）
</details>

## 📄 License

MIT License — 可自由使用、修改、商用，请保留版权声明。

---

**Made with ❤️ · 一个把「检索增强生成」做到生产级细节的饮料问答项目**

**作者：[Qingk](https://github.com/qingkongyanyu)**
