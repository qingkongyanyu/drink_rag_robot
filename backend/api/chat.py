"""对话 API：普通问答 + SSE 流式问答 + 历史管理。"""
from __future__ import annotations

import json
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.core.config import settings
from backend.core.logging import logger
from backend.models.schemas import ChatRequest, ChatResponse
from backend.services import chat_service, llm_service

router = APIRouter(prefix="/api/chat", tags=["对话"])


def _sse_event(event: str, data: dict) -> str:
    """SSE 事件：类型同时放在 event: 行与 data.type（前端两种解析都兼容）。"""
    payload = {**data, "type": event}
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(req: ChatRequest):
    """问答接口。stream=true 时返回 SSE 流式响应。"""
    try:
        if req.stream:
            return StreamingResponse(
                _stream_events(req),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
                },
            )
        result = chat_service.generate_reply(
            req.session_id, req.question, req.use_history, req.show_citations
        )
        return {"code": 200, "msg": "ok", "data": ChatResponse(**result)}
    except llm_service.LLMError as e:
        raise HTTPException(status_code=e.code, detail=e.msg)
    except Exception as e:  # noqa: BLE001
        logger.exception("聊天接口异常：%s", e)
        raise HTTPException(status_code=500, detail=f"服务内部异常：{e}")


def _stream_events(req: ChatRequest):
    try:
        for ev in chat_service.stream_reply(
            req.session_id, req.question, req.use_history, req.show_citations
        ):
            etype = ev["type"]
            if etype == "meta":
                yield _sse_event("meta", {"sources": ev["sources"], "use_knowledge": ev["use_knowledge"]})
            elif etype == "delta":
                yield _sse_event("delta", {"content": ev["content"]})
            elif etype == "error":
                yield _sse_event("error", {"message": ev["message"]})
            elif etype == "done":
                yield _sse_event(
                    "done",
                    {
                        "latency_ms": ev["latency_ms"],
                        "llm_tokens": ev["llm_tokens"],
                        "model": settings.LLM_MODEL,
                    },
                )
    except llm_service.LLMError as e:
        yield _sse_event("error", {"message": e.msg, "code": e.code})
    except Exception as e:  # noqa: BLE001
        logger.exception("流式聊天异常：%s", e)
        yield _sse_event("error", {"message": f"服务内部异常：{e}"})


@router.get("/history")
async def history(session_id: str = Query("default", max_length=64)):
    """获取会话历史消息。"""
    msgs = chat_service.get_session_messages(session_id)
    return {"code": 200, "msg": "ok", "data": msgs}


@router.post("/clear")
async def clear(body: Dict):
    """清空指定会话历史。"""
    session_id = body.get("session_id", "default")
    deleted = chat_service.clear_session(session_id)
    return {"code": 200, "msg": f"已清空 {deleted} 条消息", "data": {"deleted": deleted}}
