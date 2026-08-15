"""系统状态与统计服务：仪表盘数据聚合。"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from backend.core import database as db
from backend.core.config import settings
from backend.rag.engine import get_rag_engine

_START_TIME = time.time()


def system_status() -> Dict[str, Any]:
    engine = get_rag_engine()
    docs = db.list_docs()
    chunks = db.get_all_chunks()
    today = db.today_key()
    daily_rows = db.get_daily_stats(days=1)
    daily_qa = daily_rows[0]["qa_count"] if daily_rows else 0

    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "uptime_seconds": int(time.time() - _START_TIME),
        "api_key_configured": bool((settings.LLM_API_KEY or "").strip()),
        "llm_model": settings.LLM_MODEL,
        "engine_ready": engine.is_ready(),
        "embedding_model": engine.embeddings.model_name,
        "vector_size": engine.vector_store.size if engine.vector_store else 0,
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "conversation_count": db.get_session_count(),
        "daily_qa": daily_qa,
        "device": engine.embeddings._resolve_device(),
        "knowledge": {
            "categories": engine.stats()["categories"],
            "bm25_docs": engine.bm25.size,
            "total_bytes": engine.stats()["total_bytes"],
        },
    }


def daily_stats(days: int = 14) -> List[Dict[str, Any]]:
    return db.get_daily_stats(days=days)


def chat_stats() -> Dict[str, Any]:
    """对话维度统计：总量、日均、最近会话。"""
    daily = db.get_daily_stats(days=30)
    total_qa = sum(d["qa_count"] for d in daily)
    total_uploads = sum(d["doc_uploads"] for d in daily)
    return {
        "total_qa": total_qa,
        "total_uploads": total_uploads,
        "days_tracked": len(daily),
    }


def rag_pipeline_stats() -> Dict[str, Any]:
    """RAG 管道各环节配置展示。"""
    return {
        "top_k": settings.RAG_TOP_K,
        "retrieve_k": settings.RAG_RETRIEVE_K,
        "rerank_k": settings.RAG_RERANK_K,
        "use_reranker": settings.RAG_USE_RERANKER,
        "use_rrf": settings.RAG_USE_RRF,
        "embed_model": settings.RAG_EMBED_MODEL,
        "rerank_model": settings.RAG_RERANK_MODEL,
        "chunk_size": settings.RAG_CHUNK_SIZE,
        "chunk_overlap": settings.RAG_CHUNK_OVERLAP,
        "threshold": settings.RAG_SIMILARITY_THRESHOLD,
        "query_rewrite": settings.ENABLE_QUERY_REWRITE,
    }
