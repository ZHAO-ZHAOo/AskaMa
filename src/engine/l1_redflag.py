"""L1 Red Flag engine.

Evaluates all red-flag rules against current slot values.
If any rule matches, output an EMERGENCY_NOW exit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluator import eval_clause


@dataclass
class RedFlagResult:
    triggered: bool
    triggered_rules: list = field(default_factory=list)
    exit_type: str | None = None
    near_misses: list = field(default_factory=list)
    followup_slots: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "triggered_rules": [r.get("rule_id", "") for r in self.triggered_rules],
            "triggered_rule_details": [{"rule_id": r.get("rule_id", ""), "note": r.get("user_note", {})} for r in self.triggered_rules],
            "exit_type": self.exit_type,
            "near_misses": self.near_misses,
            "followup_slots": self.followup_slots,
        }


def evaluate_redflags(slots: dict, redflag_rules: list[dict]) -> RedFlagResult:
    """Evaluate all red-flag rules against current slots."""
    result = RedFlagResult(triggered=False)

    for rule in redflag_rules:
        condition = rule.get("condition")
        if not condition:
            continue

        eval_result = eval_clause(condition, slots)

        if eval_result is True:
            result.triggered = True
            result.triggered_rules.append(rule)
            if not result.exit_type:
                result.exit_type = rule.get("exit_type", "GO_URGENT_OG_OR_AE")
            elif result.exit_type == "CALL_AMBULANCE":
                pass  # CALL_AMBULANCE has priority
            elif rule.get("exit_type") == "CALL_AMBULANCE":
                result.exit_type = "CALL_AMBULANCE"
        elif eval_result is None:
            # Check near-miss
            nm = rule.get("near_miss_condition")
            if nm:
                nm_result = eval_clause(nm, slots)
                if nm_result is True:
                    result.near_misses.append(rule.get("rule_id", ""))
                    if rule.get("followup_slots"):
                        for s in rule["followup_slots"]:
                            if s not in result.followup_slots:
                                result.followup_slots.append(s)

    return result
