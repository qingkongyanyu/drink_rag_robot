"""大模型服务：千问 DashScope 调用（非流式 + SSE 流式 + 查询改写）。

设计要点：
1. 支持流式输出（SSE），前端打字机效果；
2. 请求超时 + 自动重试 + 明确异常分类；
3. 使用 OpenAI 兼容协议（/compatible-mode/v1），便于将来切换任意兼容模型；
4. 查询改写：多轮对话下的指代消解与意图补全。
"""
from __future__ import annotations

import json
import time
from typing import Dict, Iterator, List, Optional

import requests

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


def _check_key() -> str:
    key = (settings.LLM_API_KEY or "").strip()
    if not key or key in ("your-api-key-here", "sk-your-api-key"):
        raise LLMKeyError()
    return key


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_check_key()}",
        "Content-Type": "application/json",
    }


def _build_payload(messages: List[Dict[str, str]], stream: bool = False) -> Dict:
    return {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "stream": stream,
        "temperature": settings.LLM_TEMPERATURE,
        "top_p": settings.LLM_TOP_P,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }


def _handle_response_error(resp: requests.Response) -> None:
    if resp.status_code == 401:
        raise LLMKeyError()
    if resp.status_code == 429:
        raise LLMError("请求过于频繁，已被限流，请稍后再试")
    # 4xx：请求参数/模型问题，重试无意义，透出服务端原始信息便于排查
    if 400 <= resp.status_code < 500:
        detail = resp.text[:300]
        raise LLMError(f"大模型 API 请求被拒绝 (HTTP {resp.status_code})：{detail}")
    raise LLMConnectError(f"大模型 API 请求失败 (HTTP {resp.status_code})")


# ==================== 非流式 ====================

def chat_completion(messages: List[Dict[str, str]]) -> str:
    """一次性生成完整回答。返回文本；失败抛 LLMError。"""
    payload = _build_payload(messages, stream=False)
    last_err: Optional[LLMError] = None
    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                settings.LLM_API_URL,
                headers=_headers(),
                json=payload,
                timeout=settings.LLM_TIMEOUT,
            )
            if resp.status_code != 200:
                _handle_response_error(resp)
                continue
            data = resp.json()
            text = _extract_text(data)
            if not text:
                raise LLMEmptyError()
            return text
        except requests.exceptions.Timeout:
            last_err = LLMTimeoutError()
        except requests.exceptions.ConnectionError:
            last_err = LLMConnectError()
        except LLMError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = LLMError(str(e))
        if attempt < settings.LLM_MAX_RETRIES:
            time.sleep(0.5 * (attempt + 1))
    raise last_err or LLMError()


def _extract_text(data: dict) -> str:
    """兼容 OpenAI 协议 / DashScope 原生协议两种返回结构（含流式 delta）。"""
    choices = data.get("choices")
    if choices:
        msg = choices[0].get("message") or choices[0].get("delta") or {}
        content = msg.get("content")
        if content:
            return content
    output = data.get("output", {})
    if isinstance(output, dict):
        if output.get("text"):
            return output["text"]
        out_choices = output.get("choices")
        if out_choices:
            msg = out_choices[0].get("message") or out_choices[0].get("delta") or {}
            if msg.get("content"):
                return msg["content"]
    return ""


# ==================== 流式（SSE） ====================

def stream_chat(messages: List[Dict[str, str]]) -> Iterator[str]:
    """流式生成，yield 每个文本增量（不含 SSE 包装）。"""
    payload = _build_payload(messages, stream=True)
    resp = requests.post(
        settings.LLM_API_URL,
        headers=_headers(),
        json=payload,
        timeout=settings.LLM_TIMEOUT * 2,
        stream=True,
    )
    if resp.status_code != 200:
        _handle_response_error(resp)
    try:
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            text = _extract_text(data)
            if text:
                yield text
    finally:
        resp.close()


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
