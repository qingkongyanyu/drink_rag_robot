"""RAG 引擎总控：文档入库、向量索引、混合检索、重排、知识搜索的统一入口。

架构：
    ┌─────────────────────────────────────────────┐
    │                RAGEngine                      │
    │   add_document / remove_document / retrieve   │
    └──────┬──────────────────────┬────────────────┘
           │                      │
   ┌───────▼────────┐    ┌────────▼─────────┐
   │ EmbeddingService│    │ HybridRetriever  │
   │ (bge 语义向量)  │    │  dense + sparse  │
   └───────┬────────┘    │  + RRF + rerank   │
           │             └────────┬─────────┘
   ┌───────▼────────┐             │
   │  VectorStore   │        BM25Retriever
   │   (FAISS)      │             │
   └───────┬────────┘             │
           │                      │
   ┌───────▼──────────────────────▼──────┐
   │ SQLite (knowledge_docs/chunks 持久化) │
   └──────────────────────────────────────┘

数据流：上传文件 → 解析 → 分块 → 嵌入 → 写入 FAISS + 元数据入库 → 重建 BM25。
检索：问题 → 语义向量检索 + BM25 检索 → RRF 融合 → 交叉编码器重排 → 返回 top-k。
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.core import database as db
from backend.core.config import ROOT_DIR, settings
from backend.core.logging import logger
from backend.rag import chunker
from backend.rag.document_loader import load_file
from backend.rag.embeddings import EmbeddingService, get_embedding_service
from backend.rag.hybrid_retriever import HybridRetriever
from backend.rag.reranker import Reranker
from backend.rag.sparse_retriever import BM25Retriever
from backend.rag.vector_store import VectorStore


class RAGEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self.embeddings: EmbeddingService = get_embedding_service()
        self.vector_store: Optional[VectorStore] = None
        self.bm25 = BM25Retriever()
        self.reranker = Reranker()
        self.retriever: Optional[HybridRetriever] = None
        self.chunk_by_id: Dict[int, Dict[str, Any]] = {}   # chunk_id -> 元数据
        self._bm25_chunk_ids: List[int] = []               # BM25 语料序 -> chunk_id
        self.ready = False
        self.builtin_initialized = False

    # ==================== 生命周期 ====================

    def build(self) -> None:
        """从数据库重建索引（启动时调用，幂等）。"""
        with self._lock:
            chunks = db.get_all_chunks()
            self.chunk_by_id = {}
            texts: List[str] = []
            ids: List[int] = []
            for c in chunks:
                meta = {
                    "chunk_id": c["id"],
                    "doc_id": c["doc_id"],
                    "filename": c["filename"],
                    "file_type": c["file_type"],
                    "category": c["category"],
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                }
                self.chunk_by_id[c["id"]] = meta
                texts.append(c["content"])
                ids.append(c["id"])

            if not chunks:
                self.vector_store = VectorStore(self.embeddings.dim)
                self.bm25.build([])
                self._bm25_chunk_ids = []
            else:
                logger.info("正在为 %d 个知识块构建向量索引 ...", len(chunks))
                vectors = self.embeddings.encode_docs(texts)
                self.vector_store = VectorStore(vectors.shape[1])
                metas = [{"chunk_id": cid} for cid in ids]
                self.vector_store.add(vectors, metas)
                self.bm25.build(texts)
                self._bm25_chunk_ids = ids

            self._wire_retriever()
            self.ready = True
            logger.info(
                "RAG 引擎就绪：chunks=%d vectors=%d vocab=%d",
                len(self.chunk_by_id), self.vector_store.size, self.bm25.size,
            )

    def _wire_retriever(self) -> None:
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            bm25=self.bm25,
            chunk_by_id=self.chunk_by_id,
            reranker=self.reranker,
        )
        self.retriever.set_bm25_chunk_ids(self._bm25_chunk_ids)

    def _rebuild_sparse(self) -> None:
        """以 chunk_by_id 为准重建 BM25 语料。"""
        ordered = sorted(self.chunk_by_id.values(), key=lambda m: m["chunk_id"])
        self._bm25_chunk_ids = [m["chunk_id"] for m in ordered]
        self.bm25.build([m["content"] for m in ordered])
        if self.retriever:
            self.retriever.set_bm25_chunk_ids(self._bm25_chunk_ids)

    def is_ready(self) -> bool:
        return self.ready

    # ==================== 内置知识初始化 ====================

    def ensure_builtin(self) -> None:
        """初始化内置饮料知识库（幂等）：已有同名文档则跳过。"""
        with self._lock:
            if self.builtin_initialized:
                return
            self.builtin_initialized = True

            docs = db.list_docs()
            if any(d["file_type"] == "builtin" for d in docs):
                return
            builtin_file = ROOT_DIR / "data" / "drinks_100.txt"
            if not builtin_file.exists():
                logger.warning("内置知识库文件不存在：%s", builtin_file)
                return

            blocks = chunker.split_drink_blocks(builtin_file.read_text(encoding="utf-8"))
            doc_id = db.create_doc(
                filename="内置饮料知识库（100款）",
                file_type="builtin",
                category="内置知识库",
                size=builtin_file.stat().st_size,
                chunk_count=len(blocks),
                status="ready",
                created_at=time.time(),
                metadata="{}",
            )
            db.insert_chunks([(doc_id, i, block) for i, block in enumerate(blocks)])
            # 用统一的入库路径嵌入内置块
            self._embed_chunks(doc_id, blocks)
            logger.info("内置饮料知识库已入库：%d 块", len(blocks))

    # ==================== 文档管理 ====================

    def add_file(self, file_path: Path, category: str = "默认分类") -> Dict[str, Any]:
        """解析文件 → 分块 → 入库。返回文档信息。"""
        file_type, sections = load_file(file_path)
        size = file_path.stat().st_size

        # 1. 分块
        chunks_text: List[str] = []
        for sec in sections:
            pieces = chunker.chunk_section(
                sec, chunk_size=settings.RAG_CHUNK_SIZE, overlap=settings.RAG_CHUNK_OVERLAP
            )
            chunks_text.extend(pieces)
        if not chunks_text:
            raise ValueError("文件未解析出任何可索引的文本内容")

        # 2. 建文档记录（先置 processing，成功后再置 ready）
        doc_id = db.create_doc(
            filename=file_path.name,
            file_type=file_type,
            category=category,
            size=size,
            chunk_count=0,
            status="processing",
            created_at=time.time(),
            metadata="{}",
        )

        try:
            # 3. 写入块记录 + 嵌入向量
            chunk_rows = []
            for i, text in enumerate(chunks_text):
                chunk_rows.append((doc_id, i, text))
            db.insert_chunks(chunk_rows)
            new_chunks = db.get_chunks_by_doc(doc_id)
            self._embed_chunks(doc_id, [c["content"] for c in new_chunks])

            # 4. 更新文档状态
            db.update_doc(doc_id, chunk_count=len(chunks_text), status="ready", error="")
            db.add_upload_stat()
            self._rebuild_sparse()
            logger.info("文档入库完成：%s（%d 块，%s）", file_path.name, len(chunks_text), file_type)
        except Exception as e:
            db.update_doc(doc_id, status="failed", error=str(e)[:500])
            # 清理已写入的块
            db.delete_chunks(doc_id)
            raise

        return db.get_doc(doc_id) or {}

    def _embed_chunks(self, doc_id: int, texts: List[str]) -> None:
        """对某文档的所有块批量嵌入并写入 FAISS + 回填 vector_id。"""
        if not texts:
            return
        chunks = db.get_chunks_by_doc(doc_id)
        if not chunks:
            return
        vectors = self.embeddings.encode_docs(texts)
        metas = [{"chunk_id": c["id"]} for c in chunks]
        vec_ids = self.vector_store.add(vectors, metas)
        doc = db.get_doc(doc_id)
        for chunk, vid in zip(chunks, vec_ids):
            db.update_chunk_vector(chunk["id"], vid)
            self.chunk_by_id[chunk["id"]] = {
                "chunk_id": chunk["id"],
                "doc_id": doc_id,
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "category": doc["category"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
            }

    def remove_document(self, doc_id: int) -> None:
        """删除文档及其向量、块记录，重建稀疏索引。"""
        with self._lock:
            chunks = db.get_chunks_by_doc(doc_id)
            vec_ids = [c["vector_id"] for c in chunks if c.get("vector_id") is not None]
            if vec_ids:
                self.vector_store.soft_delete(vec_ids)
            for c in chunks:
                self.chunk_by_id.pop(c["id"], None)
            db.delete_doc(doc_id)
            self._rebuild_sparse()
            logger.info("文档已删除：doc_id=%d（%d 块）", doc_id, len(chunks))

    def remove_file_by_name(self, filename: str) -> bool:
        docs = db.list_docs()
        for d in docs:
            if d["filename"] == filename:
                self.remove_document(d["id"])
                return True
        return False

    # ==================== 检索 ====================

    def retrieve(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        """供对话使用：返回带来源信息的知识片段。"""
        if not self.is_ready():
            self.build()
        qvec = self.embeddings.encode_query(query)
        return self.retriever.retrieve(qvec, query, top_k=top_k)

    def search(self, query: str, top_k: int = 5) -> Tuple[List[Dict[str, Any]], float]:
        """供知识库搜索接口使用：返回检索耗时与结果。"""
        start = time.time()
        results = self.retrieve(query, top_k=top_k)
        elapsed = (time.time() - start) * 1000
        return results, elapsed

    # ==================== 状态 ====================

    def stats(self) -> Dict[str, Any]:
        docs = db.list_docs()
        chunks = db.get_all_chunks()
        categories: Dict[str, int] = {}
        for d in docs:
            categories[d["category"]] = categories.get(d["category"], 0) + 1
        return {
            "doc_count": len(docs),
            "chunk_count": len(chunks),
            "total_bytes": sum(d.get("size") or 0 for d in docs),
            "categories": [
                {"category": k, "doc_count": v, "chunk_count": 0} for k, v in categories.items()
            ],
            "embedding_model": self.embeddings.model_name,
            "vector_dim": self.embeddings.dim if self.embeddings.is_ready() else None,
            "vector_ready": self.vector_store is not None,
            "engine_ready": self.ready,
            "bm25_vocab": self.bm25.size,
        }

    def get_doc_text(self, doc_id: int) -> str:
        """获取文档全文（用于预览/导出）。"""
        chunks = db.get_chunks_by_doc(doc_id)
        return "\n\n".join(c["content"] for c in chunks)


_engine: Optional[RAGEngine] = None
_engine_lock = threading.Lock()


def get_rag_engine() -> RAGEngine:
    """单例。首次调用会执行 build（从 DB 重建索引）。"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                eng = RAGEngine()
                eng.build()
                _engine = eng
    return _engine
