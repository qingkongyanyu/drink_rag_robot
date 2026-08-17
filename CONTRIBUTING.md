# 🤝 贡献指南

感谢你愿意为 **Drink RAG Robot** 贡献代码！本指南帮你快速上手开发、写出符合项目规范的改动。

## 1. 环境准备

```bash
# 后端依赖（Python 3.10+）
pip install -r backend/requirements.txt

# 前端依赖（Node.js 18+，建议 20+）
cd frontend && npm install && cd ..
```

## 2. 本地开发

**后端**（热重载）：

```bash
uvicorn backend.main:app --reload --port 8002
```

**前端**（Vite 开发服务器，`/api` 已代理到 8002）：

```bash
cd frontend && npm run dev    # http://localhost:5173
```

## 3. 代码规范

| 项 | 约定 |
|----|------|
| Python 风格 | PEP 8，行宽 ≤ 100；已有模块保持与周围代码一致 |
| 类型标注 | 公开函数建议加类型标注（`from __future__ import annotations`） |
| Vue 风格 | Composition API + `<script setup>` |
| 命名 | Python `snake_case`；前端组件 `PascalCase.vue` |
| 注释 | 中文注释，解释"为什么"而非"做了什么" |

> 提示：后端模块使用 `ruff` 配置（`pyproject.toml` 已含 `[tool.ruff]`），
> 安装后可用 `ruff check backend/` 自查。

## 4. 提交约定（Conventional Commits）

```
<type>: <中文描述>

例如：
feat: 新增多轮查询改写开关
fix: 修复流式回答不出字的 SSE 解析问题
refactor: llm_service 改用 openai 官方 SDK
docs: 补充技术栈文档
test: 新增 BM25 边界用例
```

- type 可选：`feat / fix / refactor / docs / test / chore / perf / style`；
- 描述用中文，动词开头，简明扼要。

## 5. 如何提交（PR 流程）

1. 从 `main` 切新分支：`git checkout -b feat/your-feature`
2. 完成改动，本地验证通过（见下）；
3. 提交并推送：`git push origin feat/your-feature`
4. 创建 Pull Request，描述**改了什么、为什么、如何验证**；
5. 维护者 review 后合入。

## 6. 提交前必过清单

```bash
# ① 单元测试（必须全过，离线可跑）
python -m unittest backend.tests.test_rag -v

# ② 后端可导入、应用可创建
python -c "from backend.main import app; print(app.title)"

# ③ 接口冒烟测试（需先启动服务，可选）
python scripts/test_api.py
```

## 7. 文档同步

改动涉及**行为变化**（接口、参数、依赖、架构）时，请同步更新：

- `README.md`（门面，变更概览）
- `docs/技术栈.md`（新增/替换技术）
- `docs/架构设计.md`（模块/数据流变化）
- `docs/API接口文档.md`（接口契约变化）
- `docs/CHANGELOG.md`（追加一条版本记录）

新增依赖时，务必更新 `backend/requirements.txt` 与 `docs/技术栈.md` 的版本清单。
