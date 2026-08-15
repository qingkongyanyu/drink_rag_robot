"""系统 API：健康检查、运行状态、统计看板数据。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.core import database as db
from backend.core.config import settings
from backend.services import stats_service

router = APIRouter(prefix="/api/system", tags=["系统"])


@router.get("/health")
async def health():
    """健康检查（兼容旧前端）。"""
    st = stats_service.system_status()
    return {"code": 200, "msg": "ok", "data": st}


@router.get("/status")
async def status():
    """系统综合状态。"""
    st = stats_service.system_status()
    st["rag"] = stats_service.rag_pipeline_stats()
    st["chat"] = stats_service.chat_stats()
    return {"code": 200, "msg": "ok", "data": st}


@router.get("/stats/daily")
async def daily(days: int = Query(14, ge=1, le=90)):
    """按天统计（问答量/上传量/耗时）。"""
    rows = db.get_daily_stats(days=days)
    return {"code": 200, "msg": "ok", "data": rows}


@router.get("/config")
async def config_preview():
    """非敏感的配置预览（脱敏）。"""
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "llm_model": settings.LLM_MODEL,
            "embed_model": settings.RAG_EMBED_MODEL,
            "rerank_model": settings.RAG_RERANK_MODEL,
            "api_key_configured": bool((settings.LLM_API_KEY or "").strip()),
        },
    }
