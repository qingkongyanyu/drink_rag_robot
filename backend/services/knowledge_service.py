"""知识库管理服务：上传、列表、详情、删除、搜索、统计。"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core import database as db
from backend.core.config import settings
from backend.core.logging import logger
from backend.rag.engine import RAGEngine, get_rag_engine

# 文件名清洗：仅保留合法字符，防止路径穿越
_SAFE_NAME = re.compile(r"[^\w一-龥.\-]+")


def _safe_filename(name: str) -> str:
    name = Path(name).name  # 只取 basename
    return _SAFE_NAME.sub("_", name)


def _allowed(ext: str) -> bool:
    return ext.lower() in settings.knowledge_extensions_set


def save_upload(name: str, data: bytes, category: str = "默认分类") -> Dict[str, Any]:
    """保存上传文件并入库。返回文档信息；校验失败抛 ValueError。"""
    filename = _safe_filename(name)
    ext = Path(filename).suffix.lower()
    if not ext:
        raise ValueError("文件缺少扩展名，无法识别格式")
    if not _allowed(ext):
        raise ValueError(f"不支持的文件类型 {ext}，允许：{settings.KNOWLEDGE_EXTENSIONS}")
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"文件超过 {settings.MAX_UPLOAD_MB}MB 限制")

    # 唯一存储名，避免重名覆盖
    store_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    target = Path(settings.UPLOAD_DIR) / store_name
    target.write_bytes(data)

    engine = get_rag_engine()
    doc = engine.add_file(target, category=category)
    return doc


def upload_files(files: List, category: str = "默认分类") -> Dict[str, Any]:
    """批量上传。files 为 FastAPI UploadFile 列表。返回成功/失败摘要。"""
    if not files:
        raise ValueError("未接收到任何文件")
    if len(files) > settings.MAX_UPLOAD_FILES:
        raise ValueError(f"单次最多上传 {settings.MAX_UPLOAD_FILES} 个文件")

    success, failed = [], []
    for f in files:
        try:
            raw = f.file.read()
            doc = save_upload(f.filename or "未命名", raw, category)
            success.append(doc)
        except Exception as e:  # noqa: BLE001
            logger.warning("上传失败 %s：%s", getattr(f, "filename", "?"), e)
            failed.append({"filename": getattr(f, "filename", "?"), "error": str(e)})
        finally:
            try:
                f.file.close()
            except Exception:
                pass

    return {"success": success, "failed": failed, "success_count": len(success), "failed_count": len(failed)}


def list_docs() -> Dict[str, Any]:
    docs = db.list_docs()
    total_chunks = sum(d.get("chunk_count") or 0 for d in docs)
    return {"total": len(docs), "docs": docs, "total_chunks": total_chunks}


def get_doc_detail(doc_id: int) -> Optional[Dict[str, Any]]:
    doc = db.get_doc(doc_id)
    if not doc:
        return None
    chunks = db.get_chunks_by_doc(doc_id)
    return {**doc, "chunks": chunks}


def delete_doc(doc_id: int) -> bool:
    doc = db.get_doc(doc_id)
    if not doc:
        return False
    engine = get_rag_engine()
    engine.remove_document(doc_id)
    # 清理磁盘文件（内置库/在线内容无物理文件）
    try:
        for p in Path(settings.UPLOAD_DIR).glob(f"*_{doc['filename']}"):
            p.unlink(missing_ok=True)
    except Exception:
        pass
    return True


def search(query: str, top_k: int = 5) -> Dict[str, Any]:
    engine = get_rag_engine()
    results, elapsed = engine.search(query, top_k=top_k)
    return {"results": results, "total": len(results), "elapsed_ms": int(elapsed)}


def stats() -> Dict[str, Any]:
    engine = get_rag_engine()
    return engine.stats()
