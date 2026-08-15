"""交叉编码器重排模块。

使用 BAAI/bge-reranker-base 对 (query, candidate) 逐对打分，对粗召回结果精排。
- 交叉编码器精度显著高于双塔向量检索，适合候选量小的精排场景；
- 惰性加载，首次使用才下载模型；
- device 自适应 CUDA / CPU。
"""
from __future__ import annotations

import threading
from typing import List, Optional

from backend.core.config import settings
from backend.core.logging import logger

_MAX_PAIRS_PER_BATCH = 64


class Reranker:
    def __init__(self, model_name: str = None, device: str = "auto"):
        self.model_name = model_name or settings.RAG_RERANK_MODEL
        self.device = device or settings.RAG_EMBED_DEVICE
        self._model = None
        self.failed = False      # 加载失败后置位，后续直接跳过重排（优雅降级）
        self._lock = threading.Lock()

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _ensure_model(self):
        if self._model is not None or self.failed:
            return
        with self._lock:
            if self._model is not None or self.failed:
                return
            try:
                from sentence_transformers import CrossEncoder

                device = self._resolve_device()
                logger.info("加载重排模型 %s (device=%s) ...", self.model_name, device)
                self._model = CrossEncoder(
                    self.model_name, device=device, model_kwargs={"use_safetensors": True}
                )
                logger.info("重排模型就绪")
            except Exception as e:  # noqa: BLE001
                # 模型下载/加载失败 → 降级为不重排，不影响整体检索
                self.failed = True
                logger.warning("重排模型加载失败，本次将跳过重排（自动降级）：%s", e)

    def rerank(self, query: str, candidates: List[dict], top_k: int = 6) -> List[dict]:
        """对 candidates 重排。

        candidates: [{'text': str, ...其他字段}]，返回按得分降序并附加 rerank_score。
        """
        if not candidates:
            return []
        if top_k <= 0:
            return candidates
        self._ensure_model()
        if self.failed:
            return candidates[:top_k]

        pairs = [(query, c["text"]) for c in candidates]
        scores = []
        for i in range(0, len(pairs), _MAX_PAIRS_PER_BATCH):
            batch = pairs[i : i + _MAX_PAIRS_PER_BATCH]
            s = self._model.predict(batch, show_progress_bar=False)
            scores.extend(float(x) for x in s)

        for c, s in zip(candidates, scores):
            c["rerank_score"] = s

        ranked = sorted(candidates, key=lambda c: c.get("rerank_score", 0.0), reverse=True)
        return ranked[:top_k]
