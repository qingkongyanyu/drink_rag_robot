"""SQLite 持久化层。

职责：
1. 对话记录（按会话）
2. 知识库元数据（文档 / 分块）
3. 系统统计（按天的问答量、耗时、模型用量）

使用标准库 sqlite3 + WAL 模式，线程安全（每次操作独立连接）。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from backend.core.config import settings

_lock = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,                -- 'user' | 'assistant' | 'system'
    content     TEXT    NOT NULL,
    sources     TEXT    DEFAULT '[]',            -- JSON: 引用来源
    created_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, created_at);

CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    file_type   TEXT    NOT NULL,                -- txt/md/csv/json/pdf/docx
    category    TEXT    DEFAULT '默认分类',
    size        INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    status      TEXT    DEFAULT 'ready',         -- ready|processing|failed
    error       TEXT    DEFAULT '',
    created_at  REAL    NOT NULL,
    metadata    TEXT    DEFAULT '{}'             -- JSON 扩展
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content     TEXT    NOT NULL,
    vector_id   INTEGER,                          -- FAISS 中的向量编号
    created_at  REAL    NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES knowledge_docs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(doc_id);

CREATE TABLE IF NOT EXISTS stats_daily (
    day         TEXT    PRIMARY KEY,              -- 'YYYY-MM-DD'
    qa_count    INTEGER DEFAULT 0,
    total_latency_ms INTEGER DEFAULT 0,
    llm_tokens  INTEGER DEFAULT 0,
    doc_uploads INTEGER DEFAULT 0
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """初始化表结构（幂等）。"""
    with _lock:
        conn = _connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()


@contextmanager
def db_cursor() -> Iterator[sqlite3.Connection]:
    """上下文管理器：自动提交/回滚/关闭。"""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== 对话记录 ====================

def save_message(session_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None) -> int:
    with db_cursor() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, json.dumps(sources or [], ensure_ascii=False), time.time()),
        )
        return int(cur.lastrowid)


def get_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, created_at FROM conversations "
            "WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    rows = list(reversed(rows))  # 正序返回
    out = []
    for r in rows:
        try:
            sources = json.loads(r["sources"])
        except Exception:
            sources = []
        out.append({"role": r["role"], "content": r["content"], "sources": sources, "created_at": r["created_at"]})
    return out


def clear_session(session_id: str) -> int:
    with db_cursor() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
        return cur.rowcount


def get_session_count() -> int:
    with db_cursor() as conn:
        row = conn.execute("SELECT COUNT(DISTINCT session_id) c FROM conversations").fetchone()
        return int(row["c"])


# ==================== 知识库元数据 ====================

def create_doc(**fields) -> int:
    with db_cursor() as conn:
        fields.setdefault("created_at", time.time())
        keys = list(fields.keys())
        marks = ",".join("?" for _ in keys)
        sql = f"INSERT INTO knowledge_docs ({','.join(keys)}) VALUES ({marks})"
        cur = conn.execute(sql, tuple(fields[k] for k in keys))
        return int(cur.lastrowid)


def update_doc(doc_id: int, **fields) -> None:
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    with db_cursor() as conn:
        conn.execute(f"UPDATE knowledge_docs SET {sets} WHERE id=?", tuple(fields.values()) + (doc_id,))


def get_doc(doc_id: int) -> Optional[Dict[str, Any]]:
    with db_cursor() as conn:
        row = conn.execute("SELECT * FROM knowledge_docs WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = {}
        return d


def list_docs() -> List[Dict[str, Any]]:
    with db_cursor() as conn:
        rows = conn.execute("SELECT * FROM knowledge_docs ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = {}
        out.append(d)
    return out


def delete_doc(doc_id: int) -> None:
    with db_cursor() as conn:
        conn.execute("DELETE FROM knowledge_chunks WHERE doc_id=?", (doc_id,))
        conn.execute("DELETE FROM knowledge_docs WHERE id=?", (doc_id,))


def get_all_chunks() -> List[Dict[str, Any]]:
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT c.id, c.doc_id, c.chunk_index, c.content, c.vector_id, d.filename, d.file_type, d.category "
            "FROM knowledge_chunks c JOIN knowledge_docs d ON c.doc_id = d.id "
            "ORDER BY c.doc_id, c.chunk_index"
        ).fetchall()
    return [dict(r) for r in rows]


def get_chunks_by_doc(doc_id: int) -> List[Dict[str, Any]]:
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge_chunks WHERE doc_id=? ORDER BY chunk_index", (doc_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def create_chunk_row(doc_id: int, chunk_index: int, content: str, vector_id: Optional[int] = None) -> int:
    """插入单条知识块记录，返回 chunk_id。"""
    with db_cursor() as conn:
        cur = conn.execute(
            "INSERT INTO knowledge_chunks (doc_id, chunk_index, content, vector_id, created_at) VALUES (?,?,?,?,?)",
            (doc_id, chunk_index, content, vector_id, time.time()),
        )
        return int(cur.lastrowid)


def insert_chunks(rows: List[tuple]) -> None:
    """批量插入知识块：(doc_id, chunk_index, content)。"""
    if not rows:
        return
    now = time.time()
    with db_cursor() as conn:
        conn.executemany(
            "INSERT INTO knowledge_chunks (doc_id, chunk_index, content, vector_id, created_at) VALUES (?,?,?,NULL,?)",
            [(r[0], r[1], r[2], now) for r in rows],
        )


def update_chunk_vector(chunk_id: int, vector_id: Optional[int]) -> None:
    """回填 chunk 对应的 FAISS vector_id。"""
    with db_cursor() as conn:
        conn.execute("UPDATE knowledge_chunks SET vector_id=? WHERE id=?", (vector_id, chunk_id))


def delete_chunks(doc_id: int) -> None:
    with db_cursor() as conn:
        conn.execute("DELETE FROM knowledge_chunks WHERE doc_id=?", (doc_id,))


# ==================== 系统统计 ====================

def today_key() -> str:
    return time.strftime("%Y-%m-%d")


def add_qa_stat(latency_ms: int, llm_tokens: int) -> None:
    day = today_key()
    with db_cursor() as conn:
        conn.execute(
            "INSERT INTO stats_daily (day, qa_count, total_latency_ms, llm_tokens, doc_uploads) VALUES (?,1,?,?,0) "
            "ON CONFLICT(day) DO UPDATE SET "
            "qa_count=qa_count+1, total_latency_ms=total_latency_ms+?, llm_tokens=llm_tokens+?",
            (day, latency_ms, llm_tokens, latency_ms, llm_tokens),
        )


def add_upload_stat() -> None:
    day = today_key()
    with db_cursor() as conn:
        conn.execute(
            "INSERT INTO stats_daily (day, qa_count, total_latency_ms, llm_tokens, doc_uploads) VALUES (?,0,0,0,1) "
            "ON CONFLICT(day) DO UPDATE SET doc_uploads=doc_uploads+1",
            (day,),
        )


def get_daily_stats(days: int = 14) -> List[Dict[str, Any]]:
    with db_cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM stats_daily ORDER BY day DESC LIMIT ?", (days,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]
