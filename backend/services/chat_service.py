"""对话编排服务：多轮上下文、查询改写、RAG 检索、Prompt 组装、LLM 生成、结果持久化。

流程：
    提问 → 载入历史 → 查询改写 → 混合检索 → 组装 Prompt → LLM 生成 → 落库 → 统计
"""
from __future__ import annotations

import time
from typing import Dict, Iterator, List, Optional

from backend.core import database as db
from backend.core.config import settings
from backend.core.logging import logger
from backend.models.schemas import CitationItem
from backend.rag.engine import RAGEngine, get_rag_engine
from backend.services import llm_service

# 会话内历史（进程内缓存 + DB 兜底）避免每次查库
_session_buffer: Dict[str, List[Dict]] = {}


def _history_text(messages: List[Dict]) -> str:
    lines = []
    for m in messages[-settings.MAX_HISTORY_ROUNDS * 2:]:
        role = "用户" if m["role"] == "user" else "机器人"
        lines.append(f"{role}：{m['content']}")
    return "\n".join(lines)


def _load_session(session_id: str) -> List[Dict]:
    if session_id not in _session_buffer:
        _session_buffer[session_id] = db.get_messages(session_id, limit=settings.MAX_HISTORY_STORE)
    return _session_buffer[session_id]


def _format_knowledge(knowledge: List[Dict], show_citations: bool) -> str:
    if not knowledge:
        return "（知识库中未检索到相关饮料信息）"
    parts = []
    for i, item in enumerate(knowledge, start=1):
        head = f"[来源{i}]" if show_citations else f"[参考知识{i}]"
        parts.append(f"{head} {item['content']}")
    return "\n\n".join(parts)


def _format_sources(knowledge: List[Dict]) -> List[CitationItem]:
    out = []
    for i, item in enumerate(knowledge, start=1):
        out.append(CitationItem(
            doc_id=item.get("doc_id") or 0,
            filename=item.get("filename", ""),
            chunk_index=item.get("chunk_index", 0),
            score=round(item.get("score", 0.0), 4),
            snippet=item.get("content", "")[:120],
            category=item.get("category", ""),
        ))
    return out


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1 字符 ≈ 0.7 token）。仅用于统计展示。"""
    return max(1, int(len(text) * 0.7))


def _retrieve(engine: RAGEngine, query: str) -> List[Dict]:
    try:
        return engine.retrieve(query, top_k=settings.RAG_TOP_K)
    except Exception as e:  # noqa: BLE001
        logger.exception("RAG 检索失败：%s", e)
        return []


# ==================== 非流式 ====================

def generate_reply(
    session_id: str,
    question: str,
    use_history: bool = True,
    show_citations: bool = True,
) -> Dict:
    """一次性生成回答，返回 ChatResponse 字段字典。"""
    start = time.time()
    engine = get_rag_engine()

    history = _load_session(session_id) if use_history else []
    history_text = _history_text(history)

    # 1. 查询改写（多轮指代消解）
    search_query = llm_service.rewrite_query(history_text, question)
    logger.info("[chat] session=%s 改写前=%s 改写后=%s", session_id, question[:30], search_query[:30])

    # 2. 混合检索
    knowledge = _retrieve(engine, search_query)

    # 3. 组装 Prompt
    messages = _build_messages(question, history_text, knowledge, show_citations)
    bot_answer = llm_service.chat_completion(messages)

    latency = int((time.time() - start) * 1000)
    tokens = _estimate_tokens(question) + _estimate_tokens(bot_answer)

    # 4. 持久化
    _persist(session_id, question, bot_answer, knowledge, latency_ms=latency, llm_tokens=tokens)

    return {
        "session_id": session_id,
        "answer": bot_answer,
        "sources": _format_sources(knowledge),
        "latency_ms": latency,
        "llm_tokens": tokens,
        "use_knowledge": bool(knowledge),
        "model": settings.LLM_MODEL,
    }


# ==================== 流式 ====================

def stream_reply(
    session_id: str,
    question: str,
    use_history: bool = True,
    show_citations: bool = True,
) -> Iterator[Dict]:
    """流式回答。yield 事件字典：
    - {"type": "meta", "sources": [...], "use_knowledge": bool}
    - {"type": "delta", "content": str}
    - {"type": "done", "latency_ms": int, "llm_tokens": int}
    """
    start = time.time()
    engine = get_rag_engine()

    history = _load_session(session_id) if use_history else []
    history_text = _history_text(history)

    search_query = llm_service.rewrite_query(history_text, question)
    knowledge = _retrieve(engine, search_query)

    # 先把来源信息发出去，前端可即时展示“正在检索到的依据”
    yield {
        "type": "meta",
        "sources": [s.model_dump() for s in _format_sources(knowledge)],
        "use_knowledge": bool(knowledge),
        "query_rewritten": search_query,
    }

    messages = _build_messages(question, history_text, knowledge, show_citations)
    answer_parts: List[str] = []
    try:
        for delta in llm_service.stream_chat(messages):
            answer_parts.append(delta)
            yield {"type": "delta", "content": delta}
    except Exception as e:  # noqa: BLE001
        logger.exception("流式生成异常：%s", e)
        yield {"type": "error", "message": str(e)}

    bot_answer = "".join(answer_parts)
    latency = int((time.time() - start) * 1000)
    tokens = _estimate_tokens(question) + _estimate_tokens(bot_answer)
    _persist(session_id, question, bot_answer, knowledge, latency_ms=latency, llm_tokens=tokens)

    yield {"type": "done", "latency_ms": latency, "llm_tokens": tokens}


# ==================== 内部工具 ====================

def _build_messages(question: str, history_text: str, knowledge: List[Dict], show_citations: bool) -> List[Dict]:
    system = settings.LLM_SYSTEM_PROMPT
    if show_citations:
        system += "\n回答中引用知识库时，请在对应句末标注[来源N]（N 为来源编号）。"

    segments = []
    if history_text:
        segments.append(f"=== 历史对话（仅作上下文参考） ===\n{history_text}")
    segments.append(f"=== 参考知识库 ===\n{_format_knowledge(knowledge, show_citations)}")
    segments.append(f"=== 用户当前提问 ===\n{question}")
    user_content = "\n\n".join(segments)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def _persist(
    session_id: str, question: str, answer: str, knowledge: List[Dict],
    latency_ms: int = 0, llm_tokens: int = 0,
) -> None:
    """落库：用户消息 + 助手消息 + 当日统计。"""
    sources = [s.model_dump() for s in _format_sources(knowledge)]
    db.save_message(session_id, "user", question)
    db.save_message(session_id, "assistant", answer, sources)
    db.add_qa_stat(latency_ms, llm_tokens)
    # 同步会话缓冲
    buf = _session_buffer.setdefault(session_id, [])
    buf.append({"role": "user", "content": question})
    buf.append({"role": "assistant", "content": answer, "sources": sources})
    if len(buf) > settings.MAX_HISTORY_STORE * 2:
        del buf[: len(buf) - settings.MAX_HISTORY_STORE * 2]


def clear_session(session_id: str) -> int:
    _session_buffer.pop(session_id, None)
    return db.clear_session(session_id)


def get_session_messages(session_id: str) -> List[Dict]:
    return _load_session(session_id)
