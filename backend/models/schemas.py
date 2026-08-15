"""API 请求/响应 Pydantic 数据模型。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 通用 ====================

class ApiResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Any = None


# ==================== 对话 ====================

class ChatRequest(BaseModel):
    session_id: str = Field(default="default", max_length=64, description="会话ID")
    question: str = Field(..., min_length=1, max_length=800, description="用户提问")
    stream: bool = Field(default=False, description="是否流式返回")
    use_history: bool = Field(default=True, description="是否携带多轮历史")
    show_citations: bool = Field(default=True, description="是否在回答中展示引用")


class CitationItem(BaseModel):
    """回答中的引用来源。"""
    doc_id: int
    filename: str
    chunk_index: int
    score: float
    snippet: str
    category: str = ""


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[CitationItem] = Field(default_factory=list)
    latency_ms: int = 0
    llm_tokens: int = 0
    use_knowledge: bool = True
    model: str = ""


# ==================== 知识库管理 ====================

class DocInfo(BaseModel):
    id: int
    filename: str
    file_type: str
    category: str
    size: int
    chunk_count: int
    status: str
    error: str = ""
    created_at: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocListResponse(BaseModel):
    total: int
    docs: List[DocInfo]
    total_chunks: int


class ChunkInfo(BaseModel):
    id: int
    doc_id: int
    chunk_index: int
    content: str
    vector_id: Optional[int] = None
    filename: str = ""
    file_type: str = ""
    category: str = ""


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchItem(BaseModel):
    doc_id: int
    filename: str
    chunk_index: int
    content: str
    score: float
    category: str = ""
    method: str = "hybrid"  # 命中方式: dense/sparse/hybrid


class KnowledgeSearchResponse(BaseModel):
    results: List[KnowledgeSearchItem]
    total: int
    elapsed_ms: int


class CategoryStat(BaseModel):
    category: str
    doc_count: int
    chunk_count: int


class KnowledgeStatsResponse(BaseModel):
    doc_count: int
    chunk_count: int
    total_bytes: int
    categories: List[CategoryStat]
    embedding_model: str
    vector_dim: int
    vector_ready: bool
    engine_ready: bool


# ==================== 系统状态 ====================

class SystemStatusResponse(BaseModel):
    status: str = "ok"
    app_name: str = ""
    app_version: str = ""
    uptime_seconds: int = 0
    api_key_configured: bool = False
    llm_model: str = ""
    engine_ready: bool = False
    embedding_model: str = ""
    vector_size: int = 0
    doc_count: int = 0
    chunk_count: int = 0
    conversation_count: int = 0
    daily_qa: int = 0
    device: str = "cpu"
