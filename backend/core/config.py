"""全局配置中心。

设计目标：
1. 所有配置集中管理，支持通过 `.env` 文件或环境变量覆盖，禁止硬编码密钥入库。
2. 启动时自动从项目根目录读取 `.env`，找不到则使用内置默认值。
3. 使用 pydantic 做类型校验与自动转换。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# 项目根目录 = backend/..  (drink_rag_robot/)
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
VECTOR_DIR = DATA_DIR / "vector_store"
DB_PATH = DATA_DIR / "drink_rag.db"
LOG_DIR = ROOT_DIR / "logs"
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"

# 确保关键目录存在
for _d in (UPLOAD_DIR, VECTOR_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path) -> None:
    """极简 .env 解析器（避免额外依赖 python-dotenv）。

    支持 # 注释、KEY=VALUE、可选引号包裹的值；已存在的环境变量不覆盖。
    """
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv(ROOT_DIR / ".env")

# 模型下载源：默认走国内镜像（hf-mirror.com），可用 .env 的 HF_ENDPOINT 覆盖为官方源
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")


class Settings(BaseModel):
    # ---------------- 应用基础 ----------------
    APP_NAME: str = "Drink RAG Robot 饮料健康知识问答"
    APP_VERSION: str = "3.3.2"
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8002)
    DEBUG: bool = Field(default=False)
    # CORS 允许来源，逗号分隔
    CORS_ORIGINS: str = "*"

    # ---------------- 大模型（千问 DashScope） ----------------
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_MODEL: str = "qwen-plus"
    # LLM_BASE_URL：OpenAI 兼容基础地址（SDK 传入 base_url，优先采用；不含 /chat/completions）
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # LLM_API_URL：兼容旧 .env 的完整端点；llm_service 会自动去掉 /chat/completions 后缀
    LLM_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    LLM_TIMEOUT: int = 30          # 单次请求超时（秒）
    LLM_MAX_RETRIES: int = 2       # 失败重试次数
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_P: float = 0.8
    LLM_MAX_TOKENS: int = 1200
    LLM_MAX_OUTPUT_CHARS: int = 2000      # 回复文本最大字符数（流式/非流式均在输出层截断，可在 .env 覆盖）
    LLM_SYSTEM_PROMPT: str = (
        "你是一位专业、严谨的饮料健康顾问。请严格基于提供的【参考知识库】回答，"
        "禁止编造知识库中不存在的饮料信息。当知识库信息不足以回答时，明确说明'知识库中暂无相关记录'。"
        "回答要求：条理清晰、分点呈现，涵盖核心健康指标、适配人群体质、副作用、季节适配、饮用建议等关键维度；"
        "引用相关依据来源；语气专业友好，末尾可给出 1 条精炼总结。"
    )

    # ---------------- 对话 ----------------
    MAX_QUERY_CHAR: int = 800            # 单次提问最大字符
    MAX_HISTORY_ROUNDS: int = 10         # 构造上下文时携带的最近轮数
    MAX_HISTORY_STORE: int = 50          # 单会话持久化最大轮数
    ENABLE_QUERY_REWRITE: bool = True    # 是否对历史对话做查询改写（引用消解）

    # ---------------- RAG 检索 ----------------
    RAG_TOP_K: int = 4                       # 最终送入模型的文档条数
    RAG_RETRIEVE_K: int = 20                 # 混合检索阶段粗召回条数
    RAG_RERANK_K: int = 6                    # 重排后候选条数
    RAG_EMBED_MODEL: str = "BAAI/bge-small-zh"          # 中文语义嵌入（512维），本地有缓存时零下载
    RAG_EMBED_DEVICE: str = "auto"           # auto|cpu|cuda
    RAG_HYBRID_WEIGHT_DENSE: float = 0.5     # 密集向量权重（RRF时忽略）
    RAG_USE_RRF: bool = True                 # 使用 RRF 融合（否则加权求和）
    RAG_RRF_K: int = 60                      # RRF 平滑常数
    RAG_USE_RERANKER: bool = False   # 默认关闭：重排模型需联网下载（约560MB），就绪后可在 .env 开启
    RAG_RERANK_MODEL: str = "BAAI/bge-reranker-base"    # 交叉编码器重排（首次需联网下载，失败自动降级）
    RAG_SIMILARITY_THRESHOLD: float = 0.3    # 向量检索最低相似度（低于则判无命中）
    RAG_CHUNK_SIZE: int = 500                # 分块字符数
    RAG_CHUNK_OVERLAP: int = 80              # 分块重叠字符数

    # ---------------- 知识库 ----------------
    KNOWLEDGE_EXTENSIONS: str = ".txt,.md,.csv,.json,.pdf,.docx,.doc"
    MAX_UPLOAD_MB: int = 20
    MAX_UPLOAD_FILES: int = 10               # 单次最多上传文件数

    # ---------------- 数据库/路径 ----------------
    DATABASE_PATH: str = str(DB_PATH)
    UPLOAD_DIR: str = str(UPLOAD_DIR)
    VECTOR_DIR: str = str(VECTOR_DIR)

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _parse_cors(cls, v: str) -> str:
        return v.strip()

    def cors_origin_list(self) -> List[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @field_validator("RAG_EMBED_DEVICE")
    @classmethod
    def _device(cls, v: str) -> str:
        return v if v in ("auto", "cpu", "cuda") else "auto"

    @property
    def knowledge_extensions_set(self) -> set[str]:
        return {e.strip().lower() for e in self.KNOWLEDGE_EXTENSIONS.split(",") if e.strip()}


def _build_settings() -> Settings:
    """从环境变量构造 Settings。

    pydantic BaseModel 不会自动读取环境变量（那是 pydantic-settings 的能力），
    这里显式将 os.environ 中与 Settings 字段同名的键注入，使 .env 与系统环境变量均生效。
    """
    env_data = {k: os.environ[k] for k in Settings.model_fields.keys() if k in os.environ}
    return Settings(**env_data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例设置：进程内只解析一次。"""
    return _build_settings()


settings = get_settings()
