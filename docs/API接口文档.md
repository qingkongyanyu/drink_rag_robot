# 🔌 API 接口文档

> 版本：v3.3.1 · 更新日期：2026-08-17
> 交互式文档（Swagger）：启动服务后访问 `http://127.0.0.1:8000/api/docs`

**统一响应格式**：

```json
{ "code": 200, "msg": "ok", "data": { } }
```

错误时返回 HTTP 状态码 + `detail` 说明（FastAPI 标准）。

---

## 一、对话类

### 1.1 智能问答

`POST /api/chat`

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 否 | 会话 ID（默认 `default`），用于多轮记忆 |
| question | string | 是 | 用户提问（≤800 字符） |
| stream | bool | 否 | 是否流式返回（默认 false） |
| use_history | bool | 否 | 是否携带多轮历史（默认 true） |
| show_citations | bool | 否 | 回答是否带来源引用（默认 true） |

**非流式响应**（`stream:false`）：

```json
{
  "code": 200,
  "msg": "ok",
  "data": {
    "session_id": "default",
    "answer": "可口可乐含糖量较高，为 10-12g/100ml... [来源1]",
    "sources": [
      {
        "doc_id": 1, "filename": "内置饮料知识库（100款）",
        "chunk_index": 15, "score": 0.0312,
        "snippet": "饮料名称：可口可乐 ### ...", "category": "内置知识库"
      }
    ],
    "latency_ms": 1240,
    "llm_tokens": 186,
    "use_knowledge": true,
    "model": "qwen-plus"
  }
}
```

**流式响应**（`stream:true`）：`Content-Type: text/event-stream`，SSE 事件：

| 事件 | data | 说明 |
|------|------|------|
| `meta` | `{sources:[...], use_knowledge:bool}` | 检索到的引用来源（先生成） |
| `delta` | `{content:"文本片段"}` | 增量文本 |
| `done` | `{latency_ms, llm_tokens, model}` | 结束 |
| `error` | `{message, code}` | 出错 |

### 1.2 获取会话历史

`GET /api/chat/history?session_id=default`

```json
{ "code": 200, "data": [ { "role": "user", "content": "...", "sources": [], "created_at": 1755000000 } ] }
```

### 1.3 清空会话

`POST /api/chat/clear`，body：`{"session_id":"default"}`

---

## 二、知识库类

### 2.1 文档列表

`GET /api/knowledge/docs`

```json
{ "code": 200, "data": { "total": 1, "total_chunks": 100,
  "docs": [ { "id":1, "filename":"内置饮料知识库（100款）", "file_type":"builtin",
              "category":"内置知识库", "size":68311, "chunk_count":100,
              "status":"ready", "error":"", "created_at":1755000000, "metadata":{} } ] } }
```

### 2.2 上传文档

`POST /api/knowledge/upload`（multipart/form-data）

| 字段 | 说明 |
|------|------|
| files | 文件数组（≤10 个，单文件 ≤20MB） |
| category | 分类（默认"默认分类"，≤30 字符） |

支持格式：`.txt .md .csv .json .pdf .docx`

```json
{ "code": 200, "msg": "上传完成：成功 1，失败 0",
  "data": { "success_count":1, "failed_count":0,
            "success":[{"id":2,"filename":"xxx.txt","chunk_count":4,"status":"ready"}],
            "failed":[] } }
```

### 2.3 文档详情

`GET /api/knowledge/docs/{doc_id}` —— 返回文档 + 全部知识块（含 vector_id）。

### 2.4 删除文档

`DELETE /api/knowledge/docs/{doc_id}` —— 删除文档、知识块与向量（即时生效）。

### 2.5 知识库内部检索（调试）

`POST /api/knowledge/search`，body：`{"query":"可口可乐 糖尿病人","top_k":8}`

```json
{ "code": 200, "data": {
    "elapsed_ms": 8, "total": 3,
    "results": [ { "doc_id":1, "filename":"内置饮料知识库（100款）", "chunk_index":15,
                   "content":"饮料名称：可口可乐 ### ...", "score":0.0312,
                   "category":"内置知识库", "method":"hybrid" } ] } }
```

### 2.6 知识库统计

`GET /api/knowledge/stats`

```json
{ "code": 200, "data": { "doc_count":1, "chunk_count":100, "total_bytes":68311,
    "categories":[{"category":"内置知识库","doc_count":1}],
    "embedding_model":"BAAI/bge-small-zh", "vector_dim":512,
    "vector_ready":true, "engine_ready":true, "bm25_vocab":100 } }
```

---

## 三、系统类

### 3.1 健康检查

`GET /api/system/health` —— 精简状态（兼容性检查）。

### 3.2 综合状态

`GET /api/system/status`

```json
{ "code": 200, "data": {
    "status":"ok", "app_name":"Drink RAG Robot 饮料健康知识问答", "app_version":"3.3.1",
    "uptime_seconds":3600, "api_key_configured":true, "llm_model":"qwen-plus",
    "engine_ready":true, "embedding_model":"BAAI/bge-small-zh", "vector_size":100,
    "doc_count":1, "chunk_count":100, "conversation_count":5, "daily_qa":12,
    "device":"cuda",
    "rag": {"top_k":4,"retrieve_k":20,"rerank_k":6,"use_reranker":false,"use_rrf":true,
            "embed_model":"BAAI/bge-small-zh","rerank_model":"BAAI/bge-reranker-base",
            "chunk_size":500,"chunk_overlap":80,"threshold":0.3,"query_rewrite":true},
    "chat": {"total_qa":12,"total_uploads":1,"days_tracked":1} } }
```

### 3.3 按天统计

`GET /api/system/stats/daily?days=14`

```json
{ "code": 200, "data": [ { "day":"2026-08-15", "qa_count":12,
    "total_latency_ms":15200, "llm_tokens":2200, "doc_uploads":1 } ] }
```

### 3.4 配置预览（脱敏）

`GET /api/system/config` —— 非敏感的模型/应用信息。

---

## 四、错误码约定

| HTTP | 场景 |
|------|------|
| 400 | 参数错误 / 不支持的格式 / 文件过大 |
| 401 | API Key 无效或未配置 |
| 404 | 资源不存在 |
| 408 | 大模型请求超时 |
| 429 | 被限流 |
| 500 | 服务内部异常 |
| 502 | 大模型返回为空 |
| 503 | 无法连接大模型服务 |
