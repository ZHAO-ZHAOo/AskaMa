"""LLM 客户端层：阿里云千问（百炼，新加坡地域）接入。

设计原则：
1. 走 OpenAI 兼容协议，使用官方 openai SDK，只需切换 base_url / api_key / model。
2. 新加坡地域 endpoint 使用业务空间专属域名（官方推荐，性能更稳）：
       https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
   未配置 WorkspaceId 时回退国际站旧域名（仍可正常使用）：
       https://dashscope-intl.aliyuncs.com/compatible-mode/v1
3. API Key 按地域绑定：调用新加坡 endpoint 必须使用在新加坡地域创建的 API Key，
   否则返回 401 (invalid_api_key)。调用方请从百炼控制台新加坡地域获取。
4. 未配置 API Key 时返回 DummyLLM，保证 demo / CI / 无网络环境链路可跑通。
5. 本层只负责"调用 + 超时重试"，失败后的保守回退由调用方（llm.intake）处理。

环境变量：
    DASHSCOPE_API_KEY      必填（新加坡地域创建的 Key）
    DASHSCOPE_WORKSPACE_ID 业务空间 ID（在百炼控制台"业务空间详情"查看）
    LLM_BASE_URL           显式覆盖 base_url（优先级最高）
    LLM_MODEL              模型名，默认 qwen-plus
"""

from __future__ import annotations

import os
from typing import Optional

# 新加坡地域 OpenAI 兼容 base_url（业务空间专属域名，官方推荐）
DASHSCOPE_SINGAPORE_BASE_URL = (
    "https://{workspace_id}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
# 新加坡地域旧域名（无 WorkspaceId 时的回退，官方说明仍可正常使用）
DASHSCOPE_INTL_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

DEFAULT_MODEL = "qwen-plus"
DEFAULT_TIMEOUT = 60  # 秒
DEFAULT_MAX_RETRIES = 2


def _load_dotenv(path: Optional[str] = None) -> None:
    """轻量 .env 加载：只填充"尚未设置"的环境变量，不覆盖已存在的。

    默认从项目根目录（src/llm/ 上两级）找 .env；.gitignore 已忽略 .env。
    不引入 python-dotenv 依赖，支持注释行与 key=value 基础语法。
    """
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))  # src/llm
        project_root = os.path.dirname(os.path.dirname(here))  # 项目根
        path = os.path.join(project_root, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        return


# 模块导入时加载项目根目录 .env（幂等，仅填充未设置项）
_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def resolve_base_url() -> str:
    """按优先级返回 base_url：显式配置 > 新加坡业务空间域名 > 国际站旧域名。"""
    explicit = _env("LLM_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    workspace_id = _env("DASHSCOPE_WORKSPACE_ID")
    if workspace_id:
        return DASHSCOPE_SINGAPORE_BASE_URL.format(workspace_id=workspace_id)
    return DASHSCOPE_INTL_BASE_URL


class LLMClient:
    """LLM 调用抽象接口。complete() 返回模型原始文本输出（期望为 JSON 字符串）。"""

    provider: str = "base"

    def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        raise NotImplementedError("接入你的 LLM 服务商")


class DashScopeClient(LLMClient):
    """阿里云千问（百炼）客户端，OpenAI 兼容协议，默认新加坡地域。"""

    provider = "dashscope"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        from openai import OpenAI  # 延迟导入：未配置 key 时不强依赖该包

        self.api_key = api_key or _env("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY 未配置。请使用新加坡地域创建的百炼 API Key。"
            )
        self.model = model or _env("LLM_MODEL") or DEFAULT_MODEL
        self.base_url = base_url or resolve_base_url()
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        content = getattr(resp.choices[0].message, "content", None)
        return (content or "").strip()


class DummyLLM(LLMClient):
    """无 API 时的演示客户端：基于关键词返回结构正确的 JSON，让链路可跑、可测。

    仅用于本地 demo / CI / 无网络环境；生产环境请配置 DASHSCOPE_API_KEY。
    """

    provider = "dummy"

    # 与 orchestrator 原 keyword intake 一致的模块关键词表（简版）
    _MODULE_KEYWORDS = {
        "heavy_bleeding": ["出血", "量多", "血多", "heavy", "bleeding", "flow", "soak",
                           "soaking", "浸透", "换", "卫生巾", "tampon", "棉条", "血量", "很多血"],
        "severe_period_pain": ["痛", "疼", "pain", "cramp", "cramping", "痛经",
                               "肚子疼", "腹痛", "剧烈"],
        "late_or_missed_period": ["推迟", "没来", "迟到", "late", "missed", "absent",
                                  "停经", "推迟了", "还没来"],
        "irregular_or_intermenstrual_bleeding": ["不规则", "经间", "irregular",
                                                 "between", "spotting", "非经期",
                                                 "中间出血", "不规律", "周期不准"],
    }

    def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        import json

        system = messages[0]["content"] if messages else ""
        user_text = messages[-1]["content"] if messages else ""
        text_lower = (user_text or "").lower()

        module: Optional[str] = None
        scores = {}
        for mid, words in self._MODULE_KEYWORDS.items():
            scores[mid] = sum(1 for w in words if w in text_lower)
        if max(scores.values(), default=0) > 0:
            module = max(scores, key=scores.get)

        slots = {}
        if "fever" in text_lower or "发烧" in text_lower:
            if "38" in text_lower or "39" in text_lower or "量" in text_lower:
                slots["fever_status"] = {"value": "measured_fever", "confidence": 0.9}
            else:
                slots["fever_status"] = {"value": "feels_feverish_not_measured", "confidence": 0.8}
        if any(w in text_lower for w in ["晕倒", "fainted", "faint"]):
            slots["dizziness_or_fainting"] = {"value": "fainted", "confidence": 0.9}
        elif any(w in text_lower for w in ["头晕", "dizzy", "lightheaded"]):
            slots["dizziness_or_fainting"] = {"value": "lightheaded", "confidence": 0.8}
        if any(w in text_lower for w in ["怀孕", "pregnant", "两条杠"]):
            slots["pregnancy_status"] = {"value": "possibly_pregnant", "confidence": 0.8}
        if any(w in text_lower for w in ["特别多", "量很大", "much more", "very heavy"]):
            slots["flow_compared_to_usual"] = {"value": "much_more", "confidence": 0.9}
        elif any(w in text_lower for w in ["多一点", "a bit more"]):
            slots["flow_compared_to_usual"] = {"value": "a_bit_more", "confidence": 0.9}

        return json.dumps(
            {"module": module, "slots": slots, "needs_followup": True},
            ensure_ascii=False,
        )


def get_llm_client() -> LLMClient:
    """工厂：配置了新加坡地域 API Key 返回 DashScopeClient，否则返回 DummyLLM。

    显式设置 LLM_DISABLED=1 时强制返回 DummyLLM（供离线调试）。
    """
    if _env("LLM_DISABLED") == "1" or not _env("DASHSCOPE_API_KEY"):
        return DummyLLM()
    try:
        return DashScopeClient()
    except Exception:
        return DummyLLM()
