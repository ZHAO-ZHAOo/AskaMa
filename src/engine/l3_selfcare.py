"""L3 Self-care engine.

Retrieves self-care cards based on module and level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evaluator import eval_clause


@dataclass
class SelfCareOutput:
    card_ids: list = field(default_factory=list)
    cards: list = field(default_factory=list)
    includes_escalation_criteria: bool = False
    fallback_used: bool = False

    def to_dict(self) -> dict:
        return {
            "card_ids": self.card_ids,
            "includes_escalation_criteria": self.includes_escalation_criteria,
            "fallback_used": self.fallback_used,
        }


def get_selfcare(
    module: str,
    level: str,
    selfcare_cards: dict,
    slots: dict,
) -> SelfCareOutput:
    """Retrieve self-care cards for the given module and level."""
    result = SelfCareOutput()

    cards_data = selfcare_cards.get(module, {})
    cards = cards_data.get("cards", [])

    eligible = []
    for card in cards:
        # Check applicable_levels
        applicable = card.get("applicable_levels", [])
        if level not in applicable:
            continue

        # Check applies_when precondition
        applies_when = card.get("applies_when")
        if applies_when:
            cond_result = eval_clause(applies_when, slots)
            if cond_result is not True:
                continue

        eligible.append(card)

    # Sort by priority
    eligible.sort(key=lambda c: c.get("priority", 99))

    result.cards = eligible
    result.card_ids = [c.get("card_id", "") for c in eligible]
    result.includes_escalation_criteria = any(
        c.get("card_type") == "escalation_criteria" for c in eligible
    )

    if not eligible:
        result.fallback_used = True

    return result
