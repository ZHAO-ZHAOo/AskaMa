"""Intake 层：LLM 增强的模块识别 + 槽位抽取，失败自动回退关键词规则。

架构定位：
- LLM 只做"从自由文本提取结构化信息"（模块 + 槽位），不做任何分诊裁决；
  L1 红旗 / L2 决策表始终由确定性引擎完成（红牌 = 安全底座，可追责）。
- LLM 调用失败 / 未配置 Key / 输出不合法时，自动回退关键词规则
  （detect_module / extract_slots_from_text，原 orchestrator 逻辑），流程不阻塞。
- 槽位值一律按 allowed_values / range 白名单校验，不合法即丢弃（不猜），
  符合项目"阈值只认原文、分歧取保守"方针。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .client import LLMClient
from ..config_loader import ConfigBundle

# ---------------------------------------------------------------- keyword 规则（迁移自 orchestrator）

def detect_module(text: str, config: ConfigBundle) -> str | None:
    """Simple keyword-based module detection (demo substitute for LLM Intake).

    v0.4.0: 特异性加权 —— 经间出血/推迟/停经等特异性症状权重更高,
    避免通用词(如"出血")让 heavy_bleeding 在 IB/LM 场景误胜出。
    """
    text_lower = text.lower()

    keywords = {
        "heavy_bleeding": [
            "出血", "量多", "血多", "heavy", "bleeding", "flow", "soak", "soaking",
            "浸透", "换", "卫生巾", "tampon", "棉条", "血量", "很多血",
        ],
        "severe_period_pain": [
            "痛", "疼", "pain", "cramp", "cramping", "痛經", "痛经",
            "肚子疼", "腹痛", "剧烈",
        ],
        "late_or_missed_period": [
            "推迟", "迟了", "月经迟", "没来", "迟到", "late", "missed", "absent",
            "没来月经", "停经", "推迟了", "还没来",
        ],
        "irregular_or_intermenstrual_bleeding": [
            "不规则", "经间", "irregular", "between", " spotting",
            "非经期", "中间出血", "不规律", "周期不准",
            "月经之间", "之间出血", "点滴", "经期延长", "还没停", "一直没停",
            "月经结束", "经期后", "血丝",
        ],
    }

    # 特异性症状权重:经间/推迟类表述特异性高于通用"出血/痛"
    weights = {
        "irregular_or_intermenstrual_bleeding": 2,
        "late_or_missed_period": 2,
        "severe_period_pain": 1,
        "heavy_bleeding": 1,
    }

    # A negated pain phrase (for example "肚子不痛") must never make pain
    # the main complaint just because it contains the character "痛".
    pain_denied = any(phrase in text_lower for phrase in (
        "不痛", "没痛", "没有腹痛", "没有肚子疼", "无腹痛", "no pain",
    ))

    scores = {}
    for module, words in keywords.items():
        hit = sum(1 for w in words if w in text_lower)
        if module == "severe_period_pain" and pain_denied:
            hit = 0
        scores[module] = hit * weights[module]

    if max(scores.values(), default=0) == 0:
        return None

    return max(scores, key=scores.get)


def extract_slots_from_text(text: str, config: ConfigBundle) -> dict:
    """Demo slot extraction using keyword matching (substitute for LLM Intake).

    Only extracts a few key slots; real implementation uses LLM.
    """
    slots: dict[Any, dict] = {}
    text_lower = text.lower()

    # Presence/absence stated in the opening message is already useful
    # information.  Capturing it prevents the UI from asking a user who has
    # explicitly said "不痛" to later rate the pain as 0/10.
    if any(phrase in text_lower for phrase in (
        "没有腹痛", "没有肚子疼", "肚子不痛", "不腹痛", "无腹痛", "no pain",
    )):
        slots["pain_present"] = {"value": "false", "status": "answered"}
    elif any(phrase in text_lower for phrase in (
        "腹痛", "肚子疼", "肚子痛", "下腹痛", "痛经", "cramp", "cramping",
    )):
        slots["pain_present"] = {"value": "true", "status": "answered"}

    if any(phrase in text_lower for phrase in (
        "出血", "血丝", "见红", "流血", "spotting", "bleeding",
    )):
        slots["bleeding_present"] = {"value": "true", "status": "answered"}
    elif any(phrase in text_lower for phrase in (
        "没有出血", "没出血", "无出血", "no bleeding",
    )):
        slots["bleeding_present"] = {"value": "false", "status": "answered"}

    # fever_status
    # 明确给出体温数值(如"38度"、"38.5度")即视为 measured_fever,不需"量"字
    has_numeric_temp = bool(re.search(r"\d{1,2}(\.\d)?\s*(?:度|°|℃)", text_lower))
    if any(w in text_lower for w in ["发烧", "fever", "38", "39", "40"]):
        if any(w in text_lower for w in ["量", "measured", "38.", "39.", "40."]) or has_numeric_temp:
            slots["fever_status"] = {"value": "measured_fever", "status": "answered"}
        else:
            slots["fever_status"] = {"value": "feels_feverish_not_measured", "status": "answered"}

    # dizziness_or_fainting
    if any(w in text_lower for w in ["晕倒", "fainted", "faint"]):
        slots["dizziness_or_fainting"] = {"value": "fainted", "status": "answered"}
    elif any(w in text_lower for w in ["差点晕", "dizzy", "lightheaded", "头晕"]):
        slots["dizziness_or_fainting"] = {"value": "nearly_fainted", "status": "answered"}
    elif any(w in text_lower for w in ["有点晕", "lightheaded"]):
        slots["dizziness_or_fainting"] = {"value": "lightheaded", "status": "answered"}

    # heart_racing_or_short_of_breath
    if any(w in text_lower for w in ["心跳", "喘", "heart", "breath", "racing"]):
        slots["heart_racing_or_short_of_breath"] = {"value": "true", "status": "answered"}

    # vomiting
    if any(w in text_lower for w in ["吐", "vomit", "throw up"]):
        slots["vomiting_or_cannot_keep_fluids_down"] = {"value": "true", "status": "answered"}

    # bleeding_through_clothes_or_bedding
    if any(w in text_lower for w in ["裤子", "床单", "浸透衣服", "soaked through", "clothes"]):
        slots["bleeding_through_clothes_or_bedding"] = {"value": "true", "status": "answered"}

    # flow_compared_to_usual
    if any(w in text_lower for w in ["特别多", "量很大", "much more", "very heavy", "much_more"]):
        slots["flow_compared_to_usual"] = {"value": "much_more", "status": "answered"}
    elif any(w in text_lower for w in ["多一点", "a bit more"]):
        slots["flow_compared_to_usual"] = {"value": "a_bit_more", "status": "answered"}
    elif any(w in text_lower for w in ["差不多", "about the same", "same"]):
        slots["flow_compared_to_usual"] = {"value": "same", "status": "answered"}

    # pain_severity (stored as string to match question option values)
    # 显式匹配 "N分" / "N/10" / "N score",避免 str(score) in text 的误匹配
    # (如 '0' in "10分" 为真 → 曾把 10 分抽成 0 分,导致数值红旗永不触发)
    m = re.search(r"(\d{1,2})\s*(?:分|/10|score)", text_lower)
    if m:
        score = int(m.group(1))
        if 0 <= score <= 10:
            slots["pain_severity_0_10"] = {"value": str(score), "status": "answered"}
    if "pain_severity_0_10" not in slots:
        if any(w in text_lower for w in ["无法忍受", "unbearable", "worst", "剧痛", "极痛"]):
            slots["pain_severity_0_10"] = {"value": "10", "status": "answered"}
        elif any(w in text_lower for w in ["很痛", "severe", "very painful", "很疼"]):
            slots["pain_severity_0_10"] = {"value": "8", "status": "answered"}
        elif any(w in text_lower for w in ["有点痛", "mild", "slight"]):
            slots["pain_severity_0_10"] = {"value": "3", "status": "answered"}

    # pain_onset_speed
    if any(w in text_lower for w in ["突然", "sudden", "suddenly"]):
        slots["pain_onset_speed"] = {"value": "sudden", "status": "answered"}

    # pregnancy_status
    if any(w in text_lower for w in ["怀孕", "pregnant", "两条杠", "two lines"]):
        slots["pregnancy_status"] = {"value": "possibly_pregnant", "status": "answered"}

    # periods_stopped_over_12_months
    if any(w in text_lower for w in ["停经", "好久没来", "stopped", "no period for"]):
        slots["periods_stopped_over_12_months"] = {"value": "true", "status": "answered"}

    # bleeding_between_periods
    if any(w in text_lower for w in [
        "经间", "between periods", "非经期出血", "月经结束", "经期后", "月经之后",
    ]):
        slots["bleeding_between_periods"] = {"value": "true", "status": "answered"}

    # unusual_discharge_or_odor
    if any(w in text_lower for w in ["异味", "discharge", "odour", "odor", "分泌物"]):
        slots["unusual_discharge_or_odor"] = {"value": "true", "status": "answered"}

    return slots


# ---------------------------------------------------------------- LLM intake

INTAKE_SYSTEM_PROMPT_TEMPLATE = """你是"AI Grandma"——新加坡女性月经健康分诊助手的问诊信息抽取器（任务标记：INTAKE_AGENT）。
你只负责从用户主诉文本中抽取结构化信息，不回答、不建议、不诊断。

模块清单（id + 名称 + 范围）：
{modules}

可抽取槽位（id + 类型 + 描述 + 允许值）：
{slots}

抽取规则：
1. 只抽取用户"明确表达"的信息；未提及 / 不确定的槽位一律不要输出。
2. 枚举型槽位的值必须使用允许值中的 id（如 "much_more"），禁止自创值。
3. 数值型槽位输出数字（如 7、38.5）；布尔型输出 true/false；
   duration 型输出 {{"value": 数字, "unit": "hours|days|weeks"}}；date 型输出 "YYYY-MM-DD"。
4. module 从模块清单中选择最匹配的一个；无法判断时输出 null。
5. 模块选择以"最突出的症状"为准，优先级参考：
   - 疼痛/腹痛/痛经类表述 → severe_period_pain（即使同时提到出血量）
   - 出血量多/浸透/更换频繁 → heavy_bleeding
   - 推迟/没来/周期变长 → late_or_missed_period
   - 周期不规律/经间期出血/非经期出血 → irregular_or_intermenstrual_bleeding
   例："来月经肚子有点疼，和平常差不多" → 疼痛为主诉，选 severe_period_pain。
6. 严禁给出任何诊断、用药或就医建议；严禁编造用户未说的信息。
7. 只输出严格 JSON（禁止 markdown 代码块、禁止多余文字），结构为：
{{"module": "<模块id或null>", "slots": {{"<slot_id>": {{"value": <值>, "confidence": 0-1}}}}, "needs_followup": true}}"""


def _slot_allowed_text(slot: dict) -> str:
    """把单个槽位渲染成 prompt 中的一行描述。"""
    slot_id = slot.get("id")
    stype = slot.get("type")
    desc = (slot.get("description") or {}).get("zh") or (slot.get("description") or {}).get("en") or ""
    allowed = slot.get("allowed_values") or []
    if stype == "enum":
        vals = ", ".join(
            f"{av['id']}({(av.get('label') or {}).get('zh') or av['id']})" for av in allowed
        )
        return f"- {slot_id} (enum): {desc}。允许值: {vals}"
    if stype == "bool":
        return f"- {slot_id} (bool): {desc}。取值 true/false"
    if stype in ("int", "float"):
        rng = slot.get("range") or {}
        unit = slot.get("unit") or ""
        hint = f"，范围 {rng.get('min')}~{rng.get('max')}" if rng else ""
        return f"- {slot_id} ({stype}): {desc}{hint}。单位: {unit}"
    if stype == "duration":
        return f"- {slot_id} (duration): {desc}。格式 {{\"value\": 数字, \"unit\": \"hours|days|weeks\"}}"
    if stype == "date":
        return f"- {slot_id} (date): {desc}。格式 \"YYYY-MM-DD\""
    return f"- {slot_id} ({stype}): {desc}"


def build_intake_prompt(config: ConfigBundle) -> str:
    """构造 Intake system prompt（模块清单 + 全量槽位清单）。"""
    modules_text = "\n".join(
        f"- {m['id']}: {m.get('name', {}).get('zh', m['id'])}（{(m.get('scope') or {}).get('zh', '')}）"
        for m in config.modules
    )
    slots_text = "\n".join(_slot_allowed_text(s) for s in config.slots)
    return INTAKE_SYSTEM_PROMPT_TEMPLATE.format(modules=modules_text, slots=slots_text)


def parse_json(text: str) -> dict:
    """容错解析 LLM 输出：去 ```json 围栏，找第一个平衡 JSON 对象。"""
    if not text:
        return {}
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                parsed = json.loads(m.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "是", "有"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("false", "0", "否", "无"):
        return False
    return None


def _validate_slot_value(slot: dict, value: Any) -> Any | None:
    """按槽位类型白名单校验值；合法返回规范化后的值，不合法返回 None（丢弃）。"""
    stype = slot.get("type")
    allowed = slot.get("allowed_values") or []

    if stype == "enum":
        ids = {av["id"] for av in allowed}
        if isinstance(value, str) and value in ids:
            return value
        return None

    if stype == "bool":
        return _normalize_bool(value)

    if stype == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        rng = slot.get("range") or {}
        if rng.get("min") is not None and value < rng["min"]:
            return None
        if rng.get("max") is not None and value > rng["max"]:
            return None
        return value

    if stype == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        rng = slot.get("range") or {}
        if rng.get("min") is not None and value < rng["min"]:
            return None
        if rng.get("max") is not None and value > rng["max"]:
            return None
        return value

    if stype == "duration":
        if not isinstance(value, dict):
            return None
        num = value.get("value")
        unit = value.get("unit")
        if not isinstance(num, (int, float)) or isinstance(num, bool):
            return None
        if unit not in ("hours", "days", "weeks"):
            return None
        return {"value": num, "unit": unit}

    if stype == "date":
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        return None

    if stype == "text":
        return value if isinstance(value, str) and value.strip() else None

    return None


def validate_slots(payload: dict, config: ConfigBundle) -> dict:
    """校验并规范化 LLM 输出的 slots；不合法项直接丢弃（不猜）。

    Returns: {slot_id: {"value": ..., "status": "answered", "confidence": float}}
    """
    out: dict[str, dict] = {}
    raw_slots = payload.get("slots") if isinstance(payload, dict) else None
    if not isinstance(raw_slots, dict):
        return out

    for slot_id, entry in raw_slots.items():
        slot = config.get_slot(slot_id)
        if not slot:
            continue  # 未知槽位，丢弃
        if isinstance(entry, dict):
            value = entry.get("value")
            try:
                confidence = float(entry.get("confidence", 1.0))
            except (TypeError, ValueError):
                confidence = 1.0
        else:
            value = entry
            confidence = 1.0
        confidence = max(0.0, min(1.0, confidence))

        validated = _validate_slot_value(slot, value)
        if validated is None:
            continue
        out[slot_id] = {"value": validated, "status": "answered", "confidence": confidence}
    return out


@dataclass
class IntakeResult:
    """一次 intake 的结构化结果。"""

    module: Optional[str]
    slots: dict = field(default_factory=dict)
    source: str = "keyword"  # "llm" | "keyword"
    used_llm: bool = False  # 是否真实调用了 LLM
    raw: Optional[dict] = None

    @property
    def slot_count(self) -> int:
        return len(self.slots)


def keyword_intake(text: str, config: ConfigBundle) -> IntakeResult:
    """关键词规则 intake（原 orchestrator 逻辑），作为 LLM 的兜底。"""
    slots = extract_slots_from_text(text, config)
    return IntakeResult(
        module=detect_module(text, config),
        slots=slots,
        source="keyword",
        used_llm=False,
    )


def llm_intake(text: str, config: ConfigBundle, llm: LLMClient) -> Optional[IntakeResult]:
    """LLM intake：模块识别 + 槽位抽取 + 白名单校验。

    返回 None 表示调用失败或输出完全不可用（调用方回退 keyword）。
    """
    try:
        messages = [
            {"role": "system", "content": build_intake_prompt(config)},
            {"role": "user", "content": f"用户主诉：{text}"},
        ]
        raw = llm.complete(messages, temperature=0.0)
    except Exception:
        return None  # 网络 / 鉴权 / 超时等 → 回退 keyword

    parsed = parse_json(raw)
    if not parsed:
        return None

    module = parsed.get("module")
    valid_modules = set(config.module_ids)
    if module is not None and module not in valid_modules:
        module = None

    slots = validate_slots(parsed, config)
    # LLM 成功但什么都没抽出来（module=None 且无槽位）→ 视为不可用，交给 keyword
    if module is None and not slots:
        return None

    return IntakeResult(
        module=module,
        slots=slots,
        source="llm",
        used_llm=True,
        raw=parsed,
    )


def run_intake(
    text: str,
    config: ConfigBundle,
    llm: Optional[LLMClient] = None,
    enabled: bool = True,
) -> IntakeResult:
    """Intake 统一入口：优先 LLM，失败 / 未启用时回退关键词规则。

    Args:
        text: 用户本轮主诉文本。
        config: 已加载的配置。
        llm: LLM 客户端；None 或未启用时直接走关键词规则。
        enabled: LLM intake 总开关（可通过 LLM_INTAKE_ENABLED 配置）。
    """
    if enabled and llm is not None:
        result = llm_intake(text, config, llm)
        if result is not None:
            return result
    return keyword_intake(text, config)
