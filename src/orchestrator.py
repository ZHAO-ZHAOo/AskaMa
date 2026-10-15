"""Orchestrator — the main pipeline for AI Grandma.

Takes user message + session state, runs L1 → L2 → L3/L4 → Persona.
Returns FinalResponse.
Logs all events via EventLogger (anonymized, no raw text).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .config_loader import ConfigBundle
from .logger import EventLogger, create_logger
from .engine.l1_redflag import evaluate_redflags, RedFlagResult
from .engine.l2_grading import run_l2, GradingResult
from .engine.l3_selfcare import get_selfcare, SelfCareOutput
from .engine.l4_recommend import recommend_facilities, RankedPlaces
from .persona import generate_response
from .llm.intake import run_intake


@dataclass
class SessionState:
    """Per-session conversation state."""
    session_id: str
    slots: dict = field(default_factory=dict)
    asked_question_ids: list = field(default_factory=list)
    active_module: str | None = None
    stage: str = "idle"  # idle | intake | l1 | l2 | l3 | l4 | done
    level: str | None = None
    ui_language: str = "en"
    user_profile: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "slots": {k: v for k, v in self.slots.items()},
            "asked_question_ids": self.asked_question_ids,
            "active_module": self.active_module,
            "stage": self.stage,
            "level": self.level,
            "ui_language": self.ui_language,
        }


def run_pipeline(
    user_text: str,
    session: SessionState,
    config: ConfigBundle,
    is_answer: bool = False,
    answer_value: Any = None,
    logger: EventLogger | None = None,
    turn_id: int = 0,
    llm: Any = None,
    llm_intake_enabled: bool = True,
) -> dict:
    """Run one turn of the conversation pipeline.

    Args:
        user_text: The user's message text.
        session: The session state (mutated in place).
        config: The loaded config bundle.
        is_answer: Whether this message is an answer to a previous question.
        answer_value: The slot value if this is an answer.
        logger: Optional event logger.
        turn_id: Turn number for logging.
        llm: LLM 客户端（src.llm.client.LLMClient）。为 None 时 intake 走关键词规则。
        llm_intake_enabled: 是否启用 LLM intake（可经 LLM_INTAKE_ENABLED 配置）。

    Returns:
        FinalResponse dict.
    """
    events = []

    # Log user message received (anonymized — no raw text)
    if logger and not is_answer:
        logger.log(session.session_id, turn_id, "user_message_received", {
            "message_length": len(user_text),
            "is_answer": False,
        })
    elif logger and is_answer:
        logger.log(session.session_id, turn_id, "l2_question_answered", {
            "answer_provided": True,
        })

    # If answering a question, record the answer
    if is_answer and session.stage == "l2" and answer_value is not None:
        # Find the slot of the last asked question (search module tree + core questions)
        last_q_id = session.asked_question_ids[-1] if session.asked_question_ids else None
        if last_q_id and session.active_module:
            q_pool = []
            q_tree = config.question_trees.get(session.active_module, {})
            q_pool.extend(q_tree.get("questions", []))
            if config.core_questions:
                q_pool.extend(config.core_questions.get("questions", []))
            for q in q_pool:
                if q.get("question_id") == last_q_id:
                    slot_id = q.get("slot")
                    # v0.4.0: 用户回答"不确定/不知道"→ 槽位标 unknown,
                    # 使决策表 uncertainty escalate 生效(安全向升级),而非按 False 低估
                    norm = str(answer_value).replace("_", " ").replace("-", " ").lower()
                    if any(m in norm for m in ("不确定", "不知道", "不清楚", "没量", "not sure", "unsure", "unknown", "don't know")):
                        session.slots[slot_id] = {"value": None, "status": "unknown"}
                    else:
                        session.slots[slot_id] = {"value": answer_value, "status": "answered"}
                    for af in q.get("also_fills", []):
                        if af not in session.slots:
                            session.slots[af] = {"value": answer_value, "status": "answered"}
                    break
    else:
        # Intake: LLM 增强（模块识别 + 槽位抽取），失败自动回退关键词规则
        session.stage = "intake"
        intake = run_intake(
            user_text,
            config,
            llm=llm,
            enabled=llm_intake_enabled,
        )
        session.slots.update(intake.slots)

        # Detect module if not set
        if not session.active_module:
            session.active_module = intake.module

    if not session.active_module:
        female_health_words = ("月经", "经期", "姨妈", "白带", "阴道", "私处", "避孕", "妇科", "怀孕")
        if not any(word in user_text.lower() for word in female_health_words):
            return {
                "text": "亲爱的，谢谢你告诉我。但超出女性健康范畴的内容，阿嬷不太了解，建议你咨询对应的专科医生lah",
                "response_type": "out_of_scope",
                "level": None,
                "events": events,
            }
        session.active_module = "heavy_bleeding"  # 女性健康但信息不足时的安全默认路径

    # L1: Always evaluate red flags
    session.stage = "l1"
    redflag_result = evaluate_redflags(session.slots, config.redflag_rules)
    events.append({"type": "l1_evaluated", "data": redflag_result.to_dict()})

    if redflag_result.triggered:
        session.stage = "done"
        session.level = "EMERGENCY_NOW"

        # L4: Get emergency facilities
        ranked = recommend_facilities(
            config.facilities,
            "EMERGENCY_NOW",
            session.active_module,
            config.weight_presets.get("default_weights_by_level", {}),
            session.ui_language,
        )

        response = generate_response(
            level="EMERGENCY_NOW",
            module=session.active_module,
            ui_language=session.ui_language,
            redflag_result=redflag_result.to_dict(),
            ranked_places=ranked.to_dict(),
            config_bundle=config,
        )
        response["events"] = events
        if logger:
            logger.log(session.session_id, turn_id, "session_end", {
                "level": "EMERGENCY_NOW",
                "exit_type": redflag_result.exit_type,
                "triggered_rules": [r.get("rule_id", "") for r in redflag_result.triggered_rules],
            })
        return response

    # L2: Grading
    session.stage = "l2"
    q_tree = config.question_trees.get(session.active_module, {})
    d_table = config.decision_tables.get(session.active_module, {})

    grading = run_l2(
        session.active_module,
        session.slots,
        q_tree,
        d_table,
        session.asked_question_ids,
        core_questions=config.core_questions or None,
        all_decision_tables=config.decision_tables,
    )
    events.append({"type": "l2_grade_step", "data": grading.to_dict()})

    if grading.status == "in_progress" and grading.next_question:
        # Ask the next question
        session.asked_question_ids.append(grading.next_question_id)

        # Check red flags again (the question might reveal something)
        # But for now, just return the question
        lang = session.ui_language if session.ui_language in ("zh", "en") else "en"
        q = grading.next_question
        question_text = q.get("text", {}).get(lang, q.get("text", {}).get("en", ""))
        options = q.get("answer_options", [])

        options_text = []
        for opt in options:
            label = opt.get("label", {}).get(lang, opt.get("label", {}).get("en", ""))
            options_text.append({"value": opt.get("value"), "label": label})

        if logger:
            logger.log(session.session_id, turn_id, "l2_question_asked", {
                "question_id": grading.next_question_id,
                "slot": q.get("slot"),
                "module": session.active_module,
            })
        return {
            "text": question_text,
            "response_type": "question",
            "level": None,
            "question_id": grading.next_question_id,
            "slot": q.get("slot"),
            "options": options_text,
            "events": events,
        }

    # Grading is final
    session.stage = "done"
    session.level = grading.level

    if session.level == "SELF_CARE":
        # L3: Self-care
        session.stage = "l3"
        selfcare = get_selfcare(
            session.active_module,
            session.level,
            config.selfcare_cards,
            session.slots,
        )
        events.append({"type": "l3_selfcare_rendered", "data": selfcare.to_dict()})

        response = generate_response(
            level=session.level,
            module=session.active_module,
            ui_language=session.ui_language,
            selfcare_output={"cards": selfcare.cards},
            config_bundle=config,
        )
    else:
        # L4: Facility recommendation
        session.stage = "l4"
        weights_by_level = config.weight_presets.get("default_weights_by_level", {})
        ranked = recommend_facilities(
            config.facilities,
            session.level,
            session.active_module,
            weights_by_level,
            session.ui_language,
        )
        events.append({"type": "l4_ranked", "data": ranked.to_dict()})

        response = generate_response(
            level=session.level,
            module=session.active_module,
            ui_language=session.ui_language,
            ranked_places=ranked.to_dict(),
            config_bundle=config,
        )

    response["events"] = events
    if logger:
        logger.log(session.session_id, turn_id, "session_end", {
            "level": session.level,
            "module": session.active_module,
        })
    return response
