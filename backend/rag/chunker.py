"""文本分块模块。

策略：
1. 内置饮料知识：按“饮料块”（双换行分隔）切分，每块保留完整字段结构 —— 检索粒度最优。
2. 通用文档：按段落切分后，超出 chunk_size 的段落做“递归字符分块”（按标点优先、保持重叠）。
"""
from __future__ import annotations

import re
from typing import List

_SENTENCE_END = re.compile(r"(?<=[。！？!?；;])")

# 分块时优先保留的边界标点
_SPLIT_CHARS = ["。", "！", "？", "；", "]", "}", "）", ")", "\n", "，", ","]


def split_drink_blocks(text: str) -> List[str]:
    """按双换行切分饮料块，返回去空白后的块列表。"""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return blocks


def _split_sentences(text: str) -> List[str]:
    """按句子边界切分，保留标点。"""
    parts = [p for p in _SENTENCE_END.split(text) if p.strip()]
    return parts or ([text] if text.strip() else [])


def recursive_chunk(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
    min_chunk: int = 40,
) -> List[str]:
    """递归字符分块。

    - 优先在句子边界处切分，尽量不切断语义；
    - 相邻块保留 overlap 字符的重叠，减少边界信息丢失。
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        # 尝试在当前窗口内找最靠后的分隔符，让切分点更自然
        if end < n:
            best = start
            for ch in _SPLIT_CHARS:
                idx = text.rfind(ch, start + min_chunk, end)
                if idx > best:
                    best = idx
            if best > start + min_chunk:
                end = best + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + min_chunk)

    return chunks


def chunk_section(section: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """对一个自然段落做分块。段落不长则原样返回。"""
    if len(section) <= chunk_size:
        return [section]
    # 长段落先按句子拆分，再贪心合并到不超过 chunk_size
    sentences = _split_sentences(section)
    if len(sentences) <= 1:
        return recursive_chunk(section, chunk_size, overlap)

    merged: List[str] = []
    buf = ""
    for s in sentences:
        if buf and len(buf) + len(s) > chunk_size:
            merged.append(buf.strip())
            # 重叠：把上一个块尾部 overlap 字符带入下一块
            tail = buf[-overlap:] if overlap > 0 else ""
            buf = tail + s
        else:
            buf += s
    if buf.strip():
        merged.append(buf.strip())
    return [m for m in merged if m.strip()]
