"""LLM 层：客户端（阿里云千问/百炼 新加坡地域）+ Intake 增强与回退。"""

from .client import (
    LLMClient,
    DashScopeClient,
    DummyLLM,
    get_llm_client,
    resolve_base_url,
    DEFAULT_MODEL,
)
from .intake import (
    IntakeResult,
    build_intake_prompt,
    keyword_intake,
    llm_intake,
    run_intake,
    validate_slots,
)

__all__ = [
    "LLMClient",
    "DashScopeClient",
    "DummyLLM",
    "get_llm_client",
    "resolve_base_url",
    "DEFAULT_MODEL",
    "IntakeResult",
    "build_intake_prompt",
    "keyword_intake",
    "llm_intake",
    "run_intake",
    "validate_slots",
]
