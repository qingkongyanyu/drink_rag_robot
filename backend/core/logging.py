"""统一日志模块：控制台 + 滚动文件，UTF-8 安全输出（Windows 兼容）。"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.config import LOG_DIR

_configured = False


def get_logger(name: str = "drink_rag") -> logging.Logger:
    """获取带统一格式的 logger（进程内只初始化一次）。"""
    global _configured
    if not _configured:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger("drink_rag")
        root.setLevel(logging.INFO)
        root.handlers.clear()

        # 控制台 handler（Windows 兼容 UTF-8）
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)

        # 文件 handler（滚动 5MB × 5）
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _configured = True

    return logging.getLogger(name)


logger = get_logger()
