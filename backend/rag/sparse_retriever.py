"""BM25 稀疏检索（自实现，零第三方依赖）。

实现经典的 BM25 打分：
    score(q, d) = sum over t in q of IDF(t) * f(t,d) * (k1+1) / (f(t,d) + k1*(1 - b + b*|d|/avgdl))

词汇由 jieba 分词生成；语料可增量重建。规模小，直接用 numpy 向量化打分。
"""
from __future__ import annotations

import math
import threading
from typing import Dict, List, Optional, Sequence

import jieba
import numpy as np

from backend.core.logging import logger

_K1 = 1.5
_B = 0.75


class BM25Retriever:
    def __init__(self):
        self._lock = threading.RLock()
        # corpus: list[str] 与 chunks 对齐；doc_freqs: token -> 出现文档数
        self._corpus: List[str] = []
        self._tf: Optional[np.ndarray] = None        # shape (N_docs, N_terms)
        self._idf: Optional[np.ndarray] = None       # shape (N_terms,)
        self._vocab: List[str] = []
        self._vocab_index: Dict[str, int] = {}
        self._doc_lens: Optional[np.ndarray] = None
        self._avgdl: float = 0.0

    @property
    def size(self) -> int:
        return len(self._corpus)

    def _tokenize(self, text: str) -> List[str]:
        # 过滤空白 token
        return [t for t in jieba.lcut(text) if t.strip()]

    def build(self, corpus: Sequence[str]) -> None:
        """全量重建索引。"""
        with self._lock:
            self._corpus = list(corpus)
            tokenized = [self._tokenize(c) for c in self._corpus]

            vocab_set: set[str] = set()
            for toks in tokenized:
                vocab_set.update(toks)
            self._vocab = sorted(vocab_set)
            self._vocab_index = {t: i for i, t in enumerate(self._vocab)}
            N = len(tokenized)
            V = len(self._vocab)

            self._tf = np.zeros((N, V), dtype=np.float32)
            self._doc_lens = np.zeros(N, dtype=np.float32)
            doc_freq = np.zeros(V, dtype=np.float32)
            for d, toks in enumerate(tokenized):
                self._doc_lens[d] = len(toks)
                for t in set(toks):
                    if t in self._vocab_index:
                        doc_freq[self._vocab_index[t]] += 1
                for t in toks:
                    if t in self._vocab_index:
                        self._tf[d, self._vocab_index[t]] += 1.0

            self._avgdl = float(self._doc_lens.mean()) if N else 0.0
            # IDF = ln(1 + (N - df + 0.5) / (df + 0.5))，平滑避免负值
            with np.errstate(divide="ignore", invalid="ignore"):
                self._idf = np.log(1.0 + (N - doc_freq + 0.5) / (doc_freq + 0.5))
            logger.info("BM25 索引就绪：docs=%d vocab=%d avgdl=%.1f", N, V, self._avgdl)

    def search(self, query: str, top_k: int = 20, min_score: float = 0.0) -> List[Dict]:
        """返回 [{'idx': int, 'score': float}, ...] 按得分降序。"""
        with self._lock:
            if not self._corpus or self._tf is None:
                return []
            tokens = self._tokenize(query)
            terms = [t for t in tokens if t in self._vocab_index]
            if not terms:
                return []

            q_tf = np.zeros(len(self._vocab), dtype=np.float32)
            for t in terms:
                q_tf[self._vocab_index[t]] += 1.0
            present = q_tf > 0
            # BM25 分子/分母向量化
            tf_q = self._tf[:, present]
            idf_q = self._idf[present]
            denom = tf_q + _K1 * (1 - _B + _B * self._doc_lens[:, None] / max(self._avgdl, 1.0))
            scores = np.sum(tf_q * (_K1 + 1) / denom * idf_q, axis=1)

            order = np.argsort(scores)[::-1]
            results = []
            for idx in order:
                s = float(scores[idx])
                if s <= min_score:
                    continue
                results.append({"idx": int(idx), "score": s})
                if len(results) >= top_k:
                    break
            return results
