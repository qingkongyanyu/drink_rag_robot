#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
start.py - Drink RAG Robot 一键启动脚本

功能：
1. 环境自检（Python 版本 / 依赖 / API Key）
2. 若前端未构建，自动构建（需 Node.js）
3. 启动 FastAPI (Uvicorn) 服务

用法：
    python start.py
    python start.py --port 9000        # 指定端口
    python start.py --skip-build       # 跳过前端构建
"""
import os
import shutil
import subprocess
import sys

# Windows 控制台 GBK 兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")
DIST = os.path.join(FRONTEND, "dist")


def banner():
    print()
    print("  🥤  Drink RAG Robot · 饮料健康知识问答平台  v3.0")
    print("  " + "=" * 46)
    print()


def check_deps():
    try:
        import fastapi, uvicorn, sentence_transformers, faiss, jieba, requests, pydantic  # noqa: F401
    except ImportError as e:
        print(f"❌ 缺少后端依赖：{e.name}")
        print("   请先安装：python -m pip install -r backend/requirements.txt")
        sys.exit(1)


def check_api_key():
    from backend.core.config import settings

    if not (settings.LLM_API_KEY or "").strip() or "your-api-key" in settings.LLM_API_KEY:
        print("⚠️  未配置有效的 LLM_API_KEY")
        print("   请在项目根目录 .env 中填写（参考 .env.example）")
        print("   获取地址：https://dashscope.console.aliyun.com/")
        if input("   是否仍要启动？(y/n): ").strip().lower() != "y":
            sys.exit(1)


def ensure_frontend(skip_build: bool):
    if os.path.exists(os.path.join(DIST, "index.html")):
        print("✅ 前端产物已存在，直接使用。")
        return
    if skip_build:
        print("⚠️  前端未构建，跳过构建（仅 API 可用）。")
        return
    if not shutil.which("node") and not os.path.exists(os.path.join(FRONTEND, "node_modules")):
        print("❌ 未检测到 Node.js，无法构建前端。")
        print("   请安装 Node.js 后重新运行，或使用 --skip-build 仅启动 API。")
        sys.exit(1)
    print("📦 检测到前端未构建，开始构建 ...")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)
    print("✅ 前端构建完成。")


def main():
    port = 8000
    skip_build = False
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
        if a == "--skip-build":
            skip_build = True
        if a == "--help" or a == "-h":
            print(__doc__)
            sys.exit(0)

    banner()
    os.chdir(ROOT)
    check_deps()
    check_api_key()
    ensure_frontend(skip_build)

    print("🚀 启动 FastAPI 服务 ...")
    os.environ.setdefault("PORT", str(port))
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app",
           "--host", os.environ.get("HOST", "0.0.0.0"), "--port", str(port)]
    print(f"   访问地址：http://127.0.0.1:{port}")
    print(f"   API 文档：http://127.0.0.1:{port}/api/docs")
    print()
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
