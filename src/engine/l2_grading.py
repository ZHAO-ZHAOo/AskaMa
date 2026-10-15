"""L2 Grading engine.

Manages the question loop and evaluates the decision table
to produce a triage level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluator import eval_clause


SEVERITY_RANK = {
    "SELF_CARE": 1,
    "BOOK_SOON": 2,
    "SEE_DOCTOR_24_48H": 3,
    "EMERGENCY_NOW": 4,
}

ESCALATION_ORDER = ["SELF_CARE", "BOOK_SOON", "SEE_DOCTOR_24_48H", "EMERGENCY_NOW"]


@dataclass
class GradingResult:
    status: str  # in_progress | final
    level: str | None = None
    next_question_id: str | None = None
    next_question: dict | None = None
    level_trajectory: list = field(default_factory=list)
    stop_reason: str | None = None
    matched_row_id: str | None = None
    matched_module: str | None = None
    escalated_for_uncertainty: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "level": self.level,
            "next_question_id": self.next_question_id,
            "level_trajectory": self.level_trajectory,
            "stop_reason": self.stop_reason,
            "matched_row_id": self.matched_row_id,
            "matched_module": self.matched_module,
            "escalated_for_uncertainty": self.escalated_for_uncertainty,
        }


def select_next_question(
    question_tree: dict,
    slots: dict,
    asked_question_ids: list[str],
    core_questions: dict | None = None,
    module: str | None = None,
) -> dict | None:
    """Select the next question to ask based on priority and preconditions.

    v0.4.0: required_slots 答完不再提前停止——红旗相关槽位(fever/heart/vomit/dizzy 等)
    即使不在 required_slots 也必须被追问,否则 L1 红旗永远无法触发(反向死槽位)。
    已由 intake 抽取的槽位直接跳过,不重复问。
    Question order is symptom-led rather than a fixed global checklist:
    the active complaint's details come first, then the relevant safety
    screening.  This keeps "I have no pain" from turning into a long pain
    questionnaire while retaining the configured red-flag questions.
    """
    questions = question_tree.get("questions", [])
    core_qs = core_questions.get("questions", []) if core_questions else []
    module_qids = {q.get("question_id") for q in questions}
    max_q = question_tree.get("max_questions", 10)

    module_asked = [qid for qid in asked_question_ids if qid in module_qids]
    if len(module_asked) >= max_q:
        return None

    def answered_value(slot_id: str) -> Any:
        state = slots.get(slot_id)
        return state.get("value") if isinstance(state, dict) else state

    def is_false(slot_id: str) -> bool:
        value = answered_value(slot_id)
        return value is False or (isinstance(value, str) and value.lower() == "false")

    focus_by_module = {
        "heavy_bleeding": "bleeding",
        "irregular_or_intermenstrual_bleeding": "bleeding",
        "severe_period_pain": "pain",
    }
    focus = focus_by_module.get(module or "")
    focus_present_slot = {"bleeding": "bleeding_present", "pain": "pain_present"}.get(focus)

    def is_safety_question(q: dict) -> bool:
        qid = q.get("question_id", "")
        return qid.endswith(("_DIZZY", "_FEVER", "_HEART", "_VOMIT"))

    def domain_for_slot(slot_id: str | None) -> str | None:
        if not slot_id:
            return None
        if slot_id.startswith("pain_"):
            return "pain"
        if slot_id in {"flow_compared_to_usual", "current_bleeding_days_so_far", "bleeding_trigger", "bleeding_present"}:
            return "bleeding"
        if slot_id.startswith("discharge_") or slot_id == "unusual_discharge_or_odor":
            return "discharge"
        return None

    def question_group(q: dict) -> tuple[int, int]:
        """Return symptom-led group, then configuration priority."""
        qid = q.get("question_id", "")
        priority = q.get("priority", 99)
        is_core = qid in {item.get("question_id") for item in core_qs}
        domain = domain_for_slot(q.get("slot"))

        # A generic fallback has not established its presumed symptom yet:
        # ask the three short presence checks before any detailed module path.
        if focus_present_slot and answered_value(focus_present_slot) is None:
            if is_core and q.get("slot") == focus_present_slot:
                return (0, priority)
            if not is_core:
                return (3, priority)

        if not is_core:
            if is_safety_question(q):
                return (5, priority)
            return (1, priority)

        # For a bleeding complaint, finish bleeding details before asking
        # about pain; for a pain complaint, do the reverse.
        if focus and domain == focus:
            return (2, priority)
        if qid.endswith("_PRESENT"):
            return (3, priority)
        if domain:
            return (4, priority)
        return (4, priority)

    # Find unasked questions with met preconditions.
    candidates = []
    for q in list(core_qs) + list(questions):
        qid = q.get("question_id")
        if qid in asked_question_ids:
            continue

        # Skip slots already answered (e.g. extracted by intake) — avoid re-asking
        slot_id = q.get("slot")
        if slot_id and slot_id in slots:
            sv = slots[slot_id]
            status = sv.get("status") if isinstance(sv, dict) else "answered"
            if status == "answered":
                continue

        # Check precondition
        precond = q.get("precondition")
        if precond:
            precond_result = eval_clause(precond, slots)
            if precond_result is not True:
                continue

        # Do not continue a pain/bleeding-specific module after the user has
        # explicitly denied the symptom.  Other configured screening remains
        # available and grading falls back conservatively when data is absent.
        if qid in module_qids:
            if module == "severe_period_pain" and is_false("pain_present"):
                continue
            if module in {"heavy_bleeding", "irregular_or_intermenstrual_bleeding"} and is_false("bleeding_present"):
                continue

        candidates.append(q)

    if not candidates:
        return None

    candidates.sort(key=question_group)
    return candidates[0]


def grade_with_decision_table(
    decision_table: dict,
    slots: dict,
) -> tuple[str, str | None, bool]:
    """Evaluate the decision table against current slots.

    Returns (level, matched_row_id, escalated_for_uncertainty).
    """
    rows = decision_table.get("rows", [])
    conflict_resolution = decision_table.get("conflict_resolution", "highest_severity_wins")
    default_row = decision_table.get("default_row", {})
    uncertainty_policy = decision_table.get("uncertainty_policy", {})

    matched_rows = []
    uncertain_rows = []

    for row in rows:
        when = row.get("when")
        if not when:
            continue

        result = eval_clause(when, slots)

        if result is True:
            matched_rows.append(row)
        elif result is None:
            uncertain_rows.append(row)

    if matched_rows:
        if conflict_resolution == "highest_severity_wins":
            best = max(matched_rows, key=lambda r: SEVERITY_RANK.get(r.get("level", "SELF_CARE"), 0))
        else:
            best = matched_rows[0]
        return best.get("level"), best.get("row_id"), False

    # If uncertain rows exist and policy is escalate
    if uncertain_rows and uncertainty_policy.get("mode") == "escalate_one_level":
        # Pick the highest-severity uncertain row
        best = max(uncertain_rows, key=lambda r: SEVERITY_RANK.get(r.get("level", "SELF_CARE"), 0))
        base_level = best.get("level", "SELF_CARE")
        # Escalate one level, but never to EMERGENCY_NOW from L2
        # (EMERGENCY_NOW can only be triggered by L1 red flags)
        idx = ESCALATION_ORDER.index(base_level) if base_level in ESCALATION_ORDER else 0
        if idx < len(ESCALATION_ORDER) - 1:
            escalated = ESCALATION_ORDER[idx + 1]
            if escalated == "EMERGENCY_NOW":
                escalated = "SEE_DOCTOR_24_48H"
        else:
            escalated = base_level
        return escalated, best.get("row_id"), True

    # Default row
    return default_row.get("level", "BOOK_SOON"), None, False


def grade_cross_modules(
    active_module: str,
    slots: dict,
    decision_tables: dict,
) -> tuple[str | None, str | None, str]:
    """Grade other modules against explicitly matched decision-table rows.

    v0.5.0: cross-module escalation. A module other than the active one
    contributes a candidate level only when at least one of its decision-table
    rows is *definitely* matched by already-answered slots (three-valued True).
    Insufficient information is never treated as escalation here.

    Returns (level, row_id, module) of the highest-severity cross-module match,
    or (None, None, None) when no other module is explicitly triggered.
    """
    best_level: str | None = None
    best_row: str | None = None
    best_module: str | None = None

    for mod, dt in decision_tables.items():
        if mod == active_module or not dt:
            continue
        rows = dt.get("rows", [])
        matched = []
        for row in rows:
            when = row.get("when")
            if not when:
                continue
            if eval_clause(when, slots) is True:
                matched.append(row)
        if not matched:
            continue
        conflict = dt.get("conflict_resolution", "highest_severity_wins")
        if conflict == "highest_severity_wins":
            best = max(matched, key=lambda r: SEVERITY_RANK.get(r.get("level", "SELF_CARE"), 0))
        else:
            best = matched[0]
        level = best.get("level")
        if best_level is None or SEVERITY_RANK.get(level, 0) > SEVERITY_RANK.get(best_level, 0):
            best_level = level
            best_row = best.get("row_id")
            best_module = mod

    return best_level, best_row, best_module


def run_l2(
    module: str,
    slots: dict,
    question_tree: dict | None,
    decision_table: dict | None,
    asked_question_ids: list[str],
    core_questions: dict | None = None,
    all_decision_tables: dict | None = None,
) -> GradingResult:
    """Run one step of L2 grading.

    v0.5.0: the question pool merges the core screening questions with the
    active module's question tree (mixed by priority). When the module has no
    more questions to ask, the final level is the highest of (a) the active
    module's decision-table grade and (b) any explicitly matched cross-module
    rows (grade_cross_modules) — the "participate in escalation" behaviour.

    Returns a GradingResult indicating whether to ask a question or produce a final level.
    """
    result = GradingResult(status="in_progress")

    if not question_tree or not decision_table:
        result.status = "final"
        result.level = "BOOK_SOON"
        result.stop_reason = "missing_config"
        return result

    # Try to select next question (core + module pool, mixed by priority)
    next_q = select_next_question(question_tree, slots, asked_question_ids, core_questions, module)

    if next_q:
        result.next_question_id = next_q.get("question_id")
        result.next_question = next_q
        result.stop_reason = "awaiting_answer"
        return result

    # No more questions to ask — grade active module with decision table
    level, row_id, escalated = grade_with_decision_table(decision_table, slots)

    result.status = "final"
    result.level = level
    result.matched_row_id = row_id
    result.matched_module = module
    result.escalated_for_uncertainty = escalated

    # Cross-module escalation: any other module explicitly matched wins over lower severity
    if all_decision_tables:
        x_level, x_row, x_mod = grade_cross_modules(module, slots, all_decision_tables)
        if x_level and SEVERITY_RANK.get(x_level, 0) > SEVERITY_RANK.get(level, 0):
            result.level = x_level
            result.matched_row_id = x_row
            result.matched_module = x_mod
            result.escalated_for_uncertainty = False
            result.stop_reason = "cross_module_escalated"
        elif escalated:
            result.stop_reason = "uncertainty_escalated"
        else:
            result.stop_reason = "all_required_answered"
    else:
        result.stop_reason = "all_required_answered" if not escalated else "uncertainty_escalated"

    result.level_trajectory.append(result.level)

    return result
