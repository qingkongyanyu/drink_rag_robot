"""FAISS 向量库。

- 使用 IndexFlatIP（内积），嵌入向量已归一化 → 内积即余弦相似度；
- 元数据与向量一一对应（vector_id → chunk 记录）；
- 删除采用「软删除」：维护 active 集合，检索时过滤，避免重建索引；达到阈值自动重建。
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.logging import logger


class VectorStore:
    def __init__(self, dim: int):
        import faiss

        self.dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self._vectors: List[Optional[np.ndarray]] = []   # vector_id -> vec（软删除置 None）
        self._meta: List[Dict[str, Any]] = []            # vector_id -> chunk 元数据
        self._active: set[int] = set()                   # 有效 vector_id 集合
        self._next_id = 0
        self._lock = threading.RLock()
        self._max_garbage = 2000  # 软删除积累阈值，超过则重建

    # ---------------- 写操作 ----------------

    def add(self, vectors: np.ndarray, metas: List[Dict[str, Any]]) -> List[int]:
        """批量添加向量与元数据，返回 vector_id 列表。"""
        if len(vectors) == 0:
            return []
        with self._lock:
            self._index.add(vectors.astype(np.float32))
            ids = list(range(self._next_id, self._next_id + len(vectors)))
            for vec, meta in zip(vectors, metas):
                self._vectors.append(vec)
                self._meta.append(meta)
                self._active.add(self._next_id)
                self._next_id += 1
            return ids

    def soft_delete(self, vector_ids: List[int]) -> None:
        """软删除指定向量。"""
        with self._lock:
            for vid in vector_ids:
                self._active.discard(vid)
                if 0 <= vid < len(self._vectors):
                    self._vectors[vid] = None
            if len(self._vectors) - len(self._active) >= self._max_garbage:
                self.rebuild()

    def rebuild(self) -> None:
        """基于 active 向量重建 FAISS 索引（压缩空洞）。"""
        with self._lock:
            active_ids = sorted(self._active)
            if not active_ids:
                self._index = type(self._index)(self.dim)
                self._vectors, self._meta = [], []
                self._next_id = 0
                return
            mat = np.vstack([self._vectors[i] for i in active_ids]).astype(np.float32)
            import faiss

            new_index = faiss.IndexFlatIP(self.dim)
            new_index.add(mat)
            self._index = new_index
            # 重新映射：新 vector_id = 新插入序
            new_meta = [self._meta[i] for i in active_ids]
            self._vectors = [self._vectors[i] for i in active_ids]
            self._meta = new_meta
            self._active = set(range(len(active_ids)))
            self._next_id = len(active_ids)
            logger.info("向量库已重建，当前活跃向量 %d 条", len(active_ids))

    def clear(self) -> None:
        with self._lock:
            import faiss

            self._index = faiss.IndexFlatIP(self.dim)
            self._vectors, self._meta, self._active = [], [], set()
            self._next_id = 0

    # ---------------- 读操作 ----------------

    @property
    def size(self) -> int:
        return len(self._active)

    @property
    def total_stored(self) -> int:
        return self._next_id

    def get_meta(self, vector_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            if 0 <= vector_id < len(self._meta):
                return self._meta[vector_id]
            return None

    def active_vector_ids(self) -> List[int]:
        with self._lock:
            return sorted(self._active)

    def search(self, query_vec: np.ndarray, top_k: int = 20, threshold: float = 0.0) -> List[Dict]:
        """返回 [{'vector_id': int, 'score': float}, ...]（已过滤软删除项）。"""
        with self._lock:
            if self._index.ntotal == 0:
                return []
            k = min(top_k * 3 + 10, self._index.ntotal)
            scores, ids = self._index.search(np.asarray([query_vec], dtype=np.float32), k)
            results = []
            for s, vid in zip(scores[0], ids[0]):
                if int(vid) < 0:
                    continue
                if int(vid) not in self._active:
                    continue
                if float(s) < threshold:
                    continue
                results.append({"vector_id": int(vid), "score": float(s)})
                if len(results) >= top_k:
                    break
            return results
