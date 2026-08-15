"""混合检索器：密集向量（语义）+ 稀疏 BM25（字面/关键词）融合。

融合策略：
1. RRF（Reciprocal Rank Fusion，默认）：按排序位次融合，对分数尺度不敏感、鲁棒；
2. 加权求和：分数归一化后按权重线性融合（可配置）。
支持可选的交叉编码器精排，见 reranker.py。
"""
from __future__ import annotations

from typing import Any, Dict, List

from backend.core.config import settings
from backend.rag.reranker import Reranker


class HybridRetriever:
    def __init__(self, vector_store, bm25, chunk_by_id: Dict[int, Dict[str, Any]], reranker: Reranker):
        self.vs = vector_store
        self.bm25 = bm25
        self.chunk_by_id = chunk_by_id
        self.reranker = reranker

    def _to_item(self, chunk_id: int, score: float, method: str) -> Dict[str, Any]:
        meta = self.chunk_by_id.get(chunk_id, {})
        return {
            "chunk_id": chunk_id,
            "doc_id": meta.get("doc_id"),
            "filename": meta.get("filename", ""),
            "file_type": meta.get("file_type", ""),
            "category": meta.get("category", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "content": meta.get("content", ""),
            "score": float(score),
            "method": method,
        }

    def retrieve(self, query_vec, query_text: str, top_k: int = None) -> List[Dict[str, Any]]:
        """完整检索管道：召回 → 融合 → 重排。"""
        final_k = top_k or settings.RAG_TOP_K
        retrieve_k = settings.RAG_RETRIEVE_K
        rerank_k = settings.RAG_RERANK_K

        # ---------- 1. 双路召回 ----------
        dense = self.vs.search(query_vec, top_k=retrieve_k, threshold=settings.RAG_SIMILARITY_THRESHOLD)
        sparse = self.bm25.search(query_text, top_k=retrieve_k)

        dense_items: Dict[int, Dict[str, Any]] = {}
        for d in dense:
            vid = d["vector_id"]
            meta = self.vs.get_meta(vid)
            if not meta:
                continue
            cid = meta["chunk_id"]
            dense_items[cid] = self._to_item(cid, d["score"], "dense")

        sparse_items: Dict[int, Dict[str, Any]] = {}
        for s in sparse:
            cid = self.bm25_chunk_id(s["idx"])
            if cid is None or cid not in self.chunk_by_id:
                continue
            sparse_items[cid] = self._to_item(cid, s["score"], "sparse")

        if not dense_items and not sparse_items:
            return []

        # ---------- 2. 融合 ----------
        if settings.RAG_USE_RRF:
            fused = self._rrf_fuse(dense_items, sparse_items)
        else:
            fused = self._weighted_fuse(dense_items, sparse_items)

        fused_sorted = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        candidates = fused_sorted[:rerank_k]

        # ---------- 3. 交叉编码器精排 ----------
        if settings.RAG_USE_RERANKER and len(candidates) > 1:
            candidates = self.reranker.rerank(query_text, candidates, top_k=final_k)
        else:
            candidates = candidates[:final_k]

        return candidates

    # 预留：由 engine 注入 bm25 与 chunk_id 的映射关系
    _bm25_chunk_ids: List[int] = []

    def set_bm25_chunk_ids(self, ids: List[int]):
        self._bm25_chunk_ids = ids

    def bm25_chunk_id(self, idx: int) -> Any:
        if 0 <= idx < len(self._bm25_chunk_ids):
            return self._bm25_chunk_ids[idx]
        return None

    # ---------- 融合算法 ----------
    def _rrf_fuse(self, dense: Dict[int, dict], sparse: Dict[int, dict]) -> Dict[int, dict]:
        rrf_k = settings.RAG_RRF_K
        order_dense = [cid for cid in dense.keys()]
        order_sparse = [cid for cid in sparse.keys()]

        fused: Dict[int, dict] = {}
        for rank, cid in enumerate(order_dense, start=1):
            item = dense[cid]
            item["method"] = "hybrid" if cid in sparse else "dense"
            item["score"] = 1.0 / (rrf_k + rank)
            fused[cid] = item
        for rank, cid in enumerate(order_sparse, start=1):
            if cid in fused:
                fused[cid]["score"] += 1.0 / (rrf_k + rank)
                fused[cid]["method"] = "hybrid"
            else:
                item = sparse[cid]
                item["method"] = "sparse"
                item["score"] = 1.0 / (rrf_k + rank)
                fused[cid] = item
        return fused

    def _weighted_fuse(self, dense: Dict[int, dict], sparse: Dict[int, dict]) -> Dict[int, dict]:
        w_d = settings.RAG_HYBRID_WEIGHT_DENSE
        w_s = 1.0 - w_d
        max_d = max((v["score"] for v in dense.values()), default=1.0) or 1.0
        max_s = max((v["score"] for v in sparse.values()), default=1.0) or 1.0

        fused: Dict[int, dict] = {}
        for cid, item in dense.items():
            item["score"] = w_d * (item["score"] / max_d)
            item["method"] = "hybrid" if cid in sparse else "dense"
            fused[cid] = item
        for cid, item in sparse.items():
            norm = w_s * (item["score"] / max_s)
            if cid in fused:
                fused[cid]["score"] += norm
                fused[cid]["method"] = "hybrid"
            else:
                item["score"] = norm
                fused[cid] = item
        return fused
