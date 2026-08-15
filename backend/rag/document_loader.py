"""多格式文档解析模块。

支持：.txt / .md / .csv / .json / .pdf / .docx
统一输出为「文本片段列表」（自然段落），后续由 chunker 决定是否再切分。
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from backend.core.logging import logger

# 最大单文件解析字节（防御超大文件）
MAX_PARSE_BYTES = 8 * 1024 * 1024


def _safe_ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def _flatten_json(obj, prefix: str = "") -> List[str]:
    """把 JSON 结构拍平成可读的『键：值』文本行。"""
    lines: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lines.extend(_flatten_json(v, f"{prefix}{k}："))
    elif isinstance(obj, list):
        if len(obj) > 20:  # 过长的数组只保留结构摘要
            lines.append(f"{prefix}[数组，共{len(obj)}项]")
            for item in obj[:3]:
                lines.extend(_flatten_json(item, prefix + "  "))
            lines.append(f"{prefix}  ...")
        else:
            for item in obj:
                lines.extend(_flatten_json(item, prefix + "  "))
    elif obj is None:
        lines.append(f"{prefix}无")
    else:
        lines.append(f"{prefix}{str(obj)}")
    return lines


def load_file(file_path: Path) -> Tuple[str, List[str]]:
    """解析文件，返回 (检测到的类型, 文本片段列表)。未知格式抛出 ValueError。"""
    ext = _safe_ext(file_path)
    if ext == "txt":
        return "txt", _load_text(file_path)
    if ext == "md":
        return "md", _load_markdown(file_path)
    if ext == "csv":
        return "csv", _load_csv(file_path)
    if ext == "json":
        return "json", _load_json(file_path)
    if ext == "pdf":
        return "pdf", _load_pdf(file_path)
    if ext == "docx":
        return "docx", _load_docx(file_path)
    if ext == "doc":
        raise ValueError("暂不支持旧版 .doc 格式，请另存为 .docx 或 .txt 后上传")
    raise ValueError(f"不支持的文件格式：.{ext}")

    # ---- 各格式实现 ----
def _read_utf8(file_path: Path) -> str:
    """优先 UTF-8，失败回退 GBK（兼容中文旧文档）。"""
    raw = file_path.read_bytes()
    if len(raw) > MAX_PARSE_BYTES:
        raise ValueError(f"文件超过解析上限 {MAX_PARSE_BYTES // 1024 // 1024}MB")
    for enc in ("utf-8", "gb18030", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _load_text(file_path: Path) -> List[str]:
    text = _read_utf8(file_path)
    return _paragraphs(text)


def _load_markdown(file_path: Path) -> List[str]:
    text = _read_utf8(file_path)
    # 去除代码块标记/图片链接等噪音，保留正文
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return _paragraphs(text)


def _paragraphs(text: str) -> List[str]:
    """按空行切分段落，段落内清理多余空白。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    cleaned = [re.sub(r"[ \t]+", " ", p) for p in paras]
    return cleaned or [text.strip()]


def _load_csv(file_path: Path) -> List[str]:
    text = _read_utf8(file_path)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    header = rows[0]
    records: List[str] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        fields = []
        for i, cell in enumerate(row):
            label = header[i] if i < len(header) and header[i].strip() else f"字段{i + 1}"
            fields.append(f"{label}：{cell.strip()}")
        records.append("\n".join(fields))
    return records


def _load_json(file_path: Path) -> List[str]:
    text = _read_utf8(file_path)
    data = json.loads(text)
    return _flatten_json(data)


def _load_pdf(file_path: Path) -> List[str]:
    from pypdf import PdfReader  # 延迟导入，避免拖慢启动

    reader = PdfReader(str(file_path))
    pages: List[str] = []
    for i, page in enumerate(reader.pages[:300]):  # 最多解析 300 页
        content = page.extract_text() or ""
        content = content.strip()
        if content:
            pages.append(content)
    if not pages:
        raise ValueError("PDF 未解析出任何文本（可能为扫描件/图片型 PDF），请转成文本后上传")
    return pages


def _load_docx(file_path: Path) -> List[str]:
    from docx import Document  # 延迟导入

    doc = Document(str(file_path))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            line = " | ".join(cells)
            if line.strip():
                paras.append(line)
    return paras or ["（该文档未包含文本内容）"]
