"""知识库 API：文档管理（上传/列表/详情/删除）与知识检索。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.core.logging import logger
from backend.models.schemas import KnowledgeSearchRequest
from backend.services import knowledge_service

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("/docs")
async def list_docs():
    """文档列表。"""
    data = knowledge_service.list_docs()
    return {"code": 200, "msg": "ok", "data": data}


@router.post("/upload")
async def upload(
    files: List[UploadFile] = File(...),
    category: str = Form("默认分类", max_length=30),
):
    """批量上传知识文档（支持 txt/md/csv/json/pdf/docx）。"""
    try:
        data = knowledge_service.upload_files(files, category=category)
        return {"code": 200, "msg": f"上传完成：成功 {data['success_count']}，失败 {data['failed_count']}", "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("上传接口异常：%s", e)
        raise HTTPException(status_code=500, detail=f"上传失败：{e}")


@router.get("/docs/{doc_id}")
async def doc_detail(doc_id: int):
    """文档详情（含全部知识块）。"""
    doc = knowledge_service.get_doc_detail(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 200, "msg": "ok", "data": doc}


@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: int):
    """删除文档及其向量与知识块。"""
    ok = knowledge_service.delete_doc(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 200, "msg": "已删除", "data": {"id": doc_id}}


@router.post("/search")
async def search(req: KnowledgeSearchRequest):
    """知识库内部检索（调试/审查检索质量）。"""
    data = knowledge_service.search(req.query, top_k=req.top_k)
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/stats")
async def stats():
    """知识库统计信息。"""
    data = knowledge_service.stats()
    return {"code": 200, "msg": "ok", "data": data}
