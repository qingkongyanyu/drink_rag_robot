"""大模型服务：千问 DashScope 调用（openai 官方 SDK，非流式 + 流式 + 查询改写）。

设计要点：
1. 基于 openai 官方 SDK 调用 OpenAI 兼容协议（/compatible-mode/v1）：
   流式输出、超时、自动重试、连接管理全部由 SDK 内置，不再手写 HTTP/SSE 解析；
2. 只需配置 base_url 一个参数，即可切换任意 OpenAI 兼容服务商（百炼/OpenAI/Ollama/方舟等）；
3. SDK 异常按类型映射为可读的业务异常（与 HTTP 状态码一一对应）；
4. 查询改写：多轮对话下的指代消解与意图补全。
"""
from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from backend.core.config import settings
from backend.core.logging import logger

# ---------------- 业务异常（与 HTTP 状态码一一对应） ----------------


class LLMError(Exception):
    code = 500
    default_msg = "大模型服务异常"

    def __init__(self, msg: str = None):
        self.msg = msg or self.default_msg
        super().__init__(self.msg)


class LLMKeyError(LLMError):
    code = 401
    default_msg = "LLM API Key 无效或未配置，请在 .env 中配置 LLM_API_KEY"


class LLMTimeoutError(LLMError):
    code = 408
    default_msg = "大模型接口请求超时，请稍后重试"


class LLMConnectError(LLMError):
    code = 503
    default_msg = "无法连接大模型 API 服务，请检查网络"


class LLMEmptyError(LLMError):
    code = 502
    default_msg = "大模型返回内容为空"


_client: Optional[OpenAI] = None


def _check_key() -> str:
    key = (settings.LLM_API_KEY or "").strip()
    if not key or key in ("your-api-key-here", "sk-your-api-key"):
        raise LLMKeyError()
    return key


def _resolve_base_url() -> str:
    """解析 OpenAI 兼容 base_url（SDK 需要基础地址，不含 /chat/completions 后缀）。

    优先取显式配置的 LLM_BASE_URL；否则用 LLM_API_URL 并去掉端点后缀（兼容旧 .env）。
    """
    if os.environ.get("LLM_BASE_URL"):
        return os.environ["LLM_BASE_URL"].strip().rstrip("/")
    api_url = (settings.LLM_API_URL or "").strip().rstrip("/")
    if api_url.endswith("/chat/completions"):
        api_url = api_url[: -len("/chat/completions")]
    return api_url or (settings.LLM_BASE_URL or "").strip().rstrip("/")


def get_client() -> OpenAI:
    """懒加载单例 OpenAI 客户端（进程内只初始化一次）。"""
    global _client
    if _client is None:
        _check_key()
        try:
            _client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=_resolve_base_url(),
                timeout=settings.LLM_TIMEOUT,
                max_retries=settings.LLM_MAX_RETRIES,
            )
        except Exception as e:  # noqa: BLE001
            raise LLMConnectError(f"LLM 客户端初始化失败: {e}") from e
    return _client


def _map_sdk_error(e: Exception) -> LLMError:
    """将 openai SDK 异常映射为业务异常（与 HTTP 状态码一一对应）。"""
    if isinstance(e, AuthenticationError):
        return LLMKeyError(f"LLM API Key 无效或未配置：{e}")
    if isinstance(e, PermissionDeniedError):
        return LLMKeyError(f"大模型 API 无访问权限：{e}")
    if isinstance(e, RateLimitError):
        return LLMError("请求过于频繁，已被限流，请稍后再试")
    if isinstance(e, APITimeoutError):
        return LLMTimeoutError()
    if isinstance(e, APIConnectionError):
        return LLMConnectError()
    if isinstance(e, BadRequestError):
        return LLMError(f"大模型 API 请求被拒绝 (HTTP {e.status_code})：{str(e)[:300]}")
    if isinstance(e, InternalServerError):
        return LLMConnectError(f"大模型服务端错误 (HTTP {e.status_code})")
    if isinstance(e, APIStatusError):
        return LLMError(f"大模型 API 请求失败 (HTTP {e.status_code})：{str(e)[:300]}")
    if isinstance(e, OpenAIError):
        return LLMError(str(e))
    return LLMError(str(e))


# ==================== 非流式 ====================


def chat_completion(messages: List[Dict[str, str]]) -> str:
    """一次性生成完整回答。返回文本；失败抛 LLMError。"""
    try:
        resp = get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            top_p=settings.LLM_TOP_P,
            max_tokens=settings.LLM_MAX_TOKENS,
            stream=False,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise LLMEmptyError()
        return text
    except LLMError:
        raise
    except Exception as e:  # noqa: BLE001
        raise _map_sdk_error(e) from e


# ==================== 流式 ====================


def stream_chat(messages: List[Dict[str, str]]) -> Iterator[str]:
    """流式生成，yield 每个文本增量；出错抛 LLMError。"""
    try:
        stream = get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=settings.LLM_TEMPERATURE,
            top_p=settings.LLM_TOP_P,
            max_tokens=settings.LLM_MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:  # noqa: BLE001
        raise _map_sdk_error(e) from e


# ==================== 查询改写 ====================

REWRITE_PROMPT = (
    "你是一个对话上下文改写助手。请根据【对话历史】将【当前用户提问】改写为一个"
    "独立、完整、信息无缺失的检索查询，以便在知识库中检索。\n"
    "要求：\n"
    "1. 若当前提问是简单问候或不含实体检索意图，原样返回当前提问；\n"
    "2. 将指代词（它、这个、那款等）替换为历史中的具体饮料/概念；\n"
    "3. 保留全部关键条件（人群、季节、成分、副作用等）；\n"
    "4. 只输出改写后的查询本身，不要任何解释或多余文字。\n"
)


def rewrite_query(history_text: str, question: str) -> str:
    """多轮对话查询改写：把历史+问题交给 LLM 得到检索查询。失败则原样返回。"""
    if not settings.ENABLE_QUERY_REWRITE or not history_text.strip():
        return question
    try:
        messages = [
            {"role": "system", "content": REWRITE_PROMPT},
            {
                "role": "user",
                "content": f"【对话历史】\n{history_text}\n\n【当前用户提问】\n{question}",
            },
        ]
        rewritten = chat_completion(messages).strip()
        return rewritten if rewritten else question
    except Exception as e:  # noqa: BLE001
        logger.warning("查询改写失败，使用原始问题：%s", e)
        return question
