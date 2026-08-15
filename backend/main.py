"""FastAPI 应用入口。

职责：
- 应用工厂 + 全局中间件（CORS、访问日志）
- 挂载业务路由（chat / knowledge / system）
- 托管前端构建产物 frontend/dist，并做 SPA 路由回退
- 启动时初始化数据库，并在后台线程预热 RAG 引擎
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core import database as db
from backend.core.config import FRONTEND_DIST_DIR, settings
from backend.core.logging import logger
from backend.rag.engine import get_rag_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：初始化数据库 + 后台预热 RAG 引擎（不阻塞启动）。"""
    db.init_db()

    def _warm_up():
        try:
            engine = get_rag_engine()
            engine.ensure_builtin()
            logger.info("RAG 引擎预热完成（含内置知识库）")
        except Exception as e:  # noqa: BLE001
            logger.error("RAG 引擎预热失败（服务仍可启动）：%s", e)

    threading.Thread(target=_warm_up, daemon=True).start()
    logger.info("%s v%s 启动中 ...", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("服务已关闭")


app = FastAPI(
    title="Drink RAG Robot API",
    description="饮料健康知识问答机器人：FastAPI + 高级RAG（混合检索/重排）+ 千问大模型",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ---------------- 中间件 ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    import time

    start = time.time()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        logger.info(
            "%s %s -> %d (%.0fms)",
            request.method, request.url.path, response.status_code, (time.time() - start) * 1000,
        )
    return response


# ---------------- 业务路由 ----------------
from backend.api.chat import router as chat_router
from backend.api.knowledge import router as knowledge_router
from backend.api.system import router as system_router

app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(system_router)


# ---------------- 前端静态托管 ----------------
_DIST = Path(FRONTEND_DIST_DIR)

if _DIST.exists() and (_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="static-assets")

    @app.get("/")
    async def serve_index():
        # 不缓存 index.html：确保每次发布前端后用户刷新即拿到最新版本
        return FileResponse(_DIST / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 路由回退：非 /api 且非文件 → 返回 index.html。"""
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"code": 404, "msg": "接口不存在"})
        candidate = _DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html", headers={"Cache-Control": "no-cache"})
else:
    logger.warning("未找到前端构建产物 frontend/dist，仅提供 API 服务。请执行前端构建后访问。")

    @app.get("/")
    async def api_only_index():
        return JSONResponse(
            content={"code": 200, "msg": "API 服务已就绪。前端未构建，请先构建 frontend。", "docs": "/api/docs"}
        )
