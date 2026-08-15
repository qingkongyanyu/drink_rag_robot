"""向量化模块：基于 sentence-transformers 的中文语义嵌入。

模型：BAAI/bge-small-zh-v1.5（512 维，中文检索效果优秀、体量小）。
- 查询侧使用官方推荐的指令前缀，显著提升检索效果；
- 结果向量 L2 归一化，使内积 == 余弦相似度，可直接用 FAISS IndexFlatIP；
- 查询向量做简单 LRU 缓存，减少重复计算；
- 惰性加载：首次调用才下载/加载模型，避免拖慢进程启动。
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.logging import logger

# BGE 官方查询指令（中文）
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class EmbeddingService:
    def __init__(self, model_name: str = None, device: str = "auto"):
        self.model_name = model_name or settings.RAG_EMBED_MODEL
        self.device = device or settings.RAG_EMBED_DEVICE
        self._model = None
        self._dim: Optional[int] = None
        self._lock = threading.Lock()
        # 查询嵌入 LRU 缓存
        self._cache: "OrderedDict[str, np.ndarray]" = OrderedDict()
        self._cache_capacity = 256
        self._cache_lock = threading.Lock()

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._ensure_model()
        return self._dim

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _ensure_model(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer

            device = self._resolve_device()
            logger.info("加载嵌入模型 %s (device=%s) ...", self.model_name, device)
            # use_safetensors=True：避免 torch.load 在旧版 torch(<2.6) 下的安全限制（CVE-2025-32434）
            self._model = SentenceTransformer(
                self.model_name, device=device, model_kwargs={"use_safetensors": True}
            )
            get_dim = getattr(self._model, "get_embedding_dimension", None) or getattr(
                self._model, "get_sentence_embedding_dimension"
            )
            self._dim = get_dim()
            logger.info("嵌入模型就绪：dim=%d device=%s", self._dim, self._model.device)

    def is_ready(self) -> bool:
        return self._model is not None

    def encode(self, texts: List[str], normalize: bool = True, is_query: bool = False) -> np.ndarray:
        """批量编码。query 侧自动加指令前缀。"""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        self._ensure_model()

        prepared = []
        cache_hits = []
        for t in texts:
            key = t
            if is_query:
                key = QUERY_INSTRUCTION + t
            hit = self._cache_get(key)
            if hit is not None:
                cache_hits.append(hit)
                prepared.append(None)
            else:
                prepared.append(key)

        need_encode = [p for p in prepared if p is not None]
        new_vecs = None
        if need_encode:
            new_vecs = self._model.encode(
                need_encode,
                normalize_embeddings=normalize,
                convert_to_numpy=True,
                batch_size=32,
                show_progress_bar=False,
            ).astype(np.float32)
            for key, vec in zip(need_encode, new_vecs):
                self._cache_put(key, vec)

        out = []
        idx = 0
        for item in prepared:
            if item is None:
                out.append(cache_hits[idx]); idx += 1
            else:
                out.append(new_vecs[list(need_encode).index(item)])
        return np.vstack(out) if out else np.zeros((0, self.dim), dtype=np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([text], is_query=True)[0]

    def encode_docs(self, texts: List[str]) -> np.ndarray:
        return self.encode(texts, is_query=False)

    # ---- LRU 缓存 ----
    def _cache_get(self, key: str) -> Optional[np.ndarray]:
        with self._cache_lock:
            val = self._cache.get(key)
            if val is not None:
                self._cache.move_to_end(key)
            return val

    def _cache_put(self, key: str, value: np.ndarray):
        with self._cache_lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_capacity:
                self._cache.popitem(last=False)


_embedding_service: Optional[EmbeddingService] = None
_embedding_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        with _embedding_lock:
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service
