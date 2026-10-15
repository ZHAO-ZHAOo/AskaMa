"""Three-valued logic condition evaluator for AI Grandma engines.

Supports: all_of, any_of, not, and single-clause conditions.
Operators: eq, ne, gt, gte, ge, lt, lte, le, in, not_in, contains_any, is_answered.
Returns True, False, or None (unknown) for three-valued logic.
"""

from __future__ import annotations

from typing import Any


def _coerce_numeric(a: Any, b: Any) -> tuple[Any, Any]:
    """Try to coerce both values to numbers for comparison."""
    def _to_num(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return v
        return v
    return _to_num(a), _to_num(b)


def eval_clause(clause: dict, slots: dict) -> bool | None:
    """Evaluate a single condition clause.

    Returns True, False, or None (unknown).
    """
    if "all_of" in clause:
        results = [eval_clause(c, slots) for c in clause["all_of"]]
        if None in results:
            if not any(r is False for r in results):
                return None
        return all(r is True for r in results)

    if "any_of" in clause:
        results = [eval_clause(c, slots) for c in clause["any_of"]]
        if any(r is True for r in results):
            return True
        if all(r is False for r in results):
            return False
        return None

    if "not" in clause:
        inner = eval_clause(clause["not"], slots)
        if inner is None:
            return None
        return not inner

    slot_id = clause.get("slot")
    if not slot_id:
        return None

    op = clause.get("op", "eq")
    expected = clause.get("value")

    slot_state = slots.get(slot_id)
    if slot_state is None:
        return None

    if isinstance(slot_state, dict):
        status = slot_state.get("status", "answered")
        value = slot_state.get("value")
    else:
        status = "answered"
        value = slot_state

    if status in ("not_asked", "unknown"):
        return None

    if status == "declined":
        return None

    if op == "is_answered":
        return True

    if op == "is_unknown":
        return False

    if op == "is_declined":
        return False

    # For bool slots, normalize string "true"/"false" to boolean
    if isinstance(expected, bool):
        if isinstance(value, str):
            value = value.lower() == "true"

    if op == "eq":
        return value == expected
    if op == "ne":
        return value != expected

    # Numeric comparisons
    if op in ("gt", "gte", "ge", "lt", "lte", "le"):
        v_coerced, e_coerced = _coerce_numeric(value, expected)
        try:
            if op == "gt":
                return v_coerced > e_coerced
            if op in ("gte", "ge"):
                return v_coerced >= e_coerced
            if op == "lt":
                return v_coerced < e_coerced
            if op in ("lte", "le"):
                return v_coerced <= e_coerced
        except TypeError:
            return None

    if op == "in":
        # Normalize string bool values
        if isinstance(expected, list):
            norm_expected = []
            for e in expected:
                if isinstance(e, bool) and isinstance(value, str):
                    norm_expected.append("true" if e else "false")
                else:
                    norm_expected.append(e)
            return value in norm_expected
        return value in expected if isinstance(expected, (list, set, tuple)) else False

    if op == "not_in":
        if isinstance(expected, list):
            norm_expected = []
            for e in expected:
                if isinstance(e, bool) and isinstance(value, str):
                    norm_expected.append("true" if e else "false")
                else:
                    norm_expected.append(e)
            return value not in norm_expected
        return value not in expected if isinstance(expected, (list, set, tuple)) else False

    if op == "contains_any":
        if not isinstance(value, list):
            value = [value]
        return any(v in expected for v in value)

    return None
