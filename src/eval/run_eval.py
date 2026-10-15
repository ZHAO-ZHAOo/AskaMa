"""Evaluation runner for AI Grandma.

Loads synthetic cases from docs/content/cases_*.md,
runs them through the pipeline, and compares expected vs actual levels.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.orchestrator import SessionState, run_pipeline


@dataclass
class TestCase:
    case_id: str
    module: str
    input_text: str
    answers: dict  # {slot_id: value} — 按槽位名匹配,避免与 intake 抽取/问题顺序冲突
    expected_level: str
    expected_redflag: str | None = None
    expected_exit: str | None = None


@dataclass
class TestResult:
    case_id: str
    expected_level: str
    actual_level: str
    correct: bool
    is_under_triage: bool
    is_over_triage: bool


SEVERITY_RANK = {
    "SELF_CARE": 1,
    "BOOK_SOON": 2,
    "SEE_DOCTOR_24_48H": 3,
    "EMERGENCY_NOW": 4,
}

# v0.5.0: core screening questions are asked regardless of the chief complaint.
# Eval cases describe a single-module scenario, so core screening gets a
# conservative "no additional symptom" default unless the case overrides it.
CORE_SLOT_DEFAULTS = {
    "pain_present": "false",
    "bleeding_present": "false",
    "unusual_discharge_or_odor": "false",
    "pain_location": "lower_abdomen_middle",
    "pain_quality": "cramping",
    "pain_duration": "1_to_2_days",
    "pain_severity_0_10": "0",
    "flow_compared_to_usual": "same",
    "current_bleeding_days_so_far": "3",
    "bleeding_trigger": "none_identified",
    "discharge_color_consistency": "clear",
    "discharge_odor": "none",
    "discharge_amount": "normal",
}


def parse_cases_file(filepath: Path) -> list[TestCase]:
    """Parse a cases markdown file into test cases."""
    content = filepath.read_text(encoding="utf-8")
    cases = []
    module = filepath.stem.replace("cases_", "")

    # Split by ## Case header lines
    case_blocks = re.split(r"^## (Case .*)$", content, flags=re.MULTILINE)

    for i in range(1, len(case_blocks), 2):
        header = case_blocks[i].strip()
        body = case_blocks[i + 1].strip() if i + 1 < len(case_blocks) else ""

        case_id = header

        # Expected level: try from header after →, then from body
        arrow_match = re.search(r"→\s*([A-Z_0-9]+)", header)
        if arrow_match:
            expected_level = arrow_match.group(1)
        else:
            level_match = re.search(r"期望级别：\s*\*{0,2}([A-Z_0-9]+)\*{0,2}", body)
            expected_level = level_match.group(1) if level_match else "UNKNOWN"

        # Extract input text
        input_match = re.search(r'输入：\s*["\']?(.*?)["\']?\s*$', body, re.MULTILINE)
        input_text = input_match.group(1).strip() if input_match else ""

        # Extract answers — {slot_id: value}, slot names from the answers dict
        answers = {}
        answer_match = re.search(r"追问回答：\s*(.*)", body)
        if answer_match:
            answer_str = answer_match.group(1).strip()
            for pair in re.findall(r"(\w+)=(\w+)", answer_str):
                answers[pair[0]] = pair[1]

        redflag_match = re.search(r"期望红旗：\s*(.*)", body)
        exit_match = re.search(r"期望出口：\s*(\w+)", body)

        cases.append(TestCase(
            case_id=case_id,
            module=module,
            input_text=input_text,
            answers=answers,
            expected_level=expected_level,
            expected_redflag=redflag_match.group(1).strip() if redflag_match else None,
            expected_exit=exit_match.group(1) if exit_match else None,
        ))

    return cases


def run_case(case: TestCase, config) -> TestResult:
    """Run a single test case through the pipeline."""
    session = SessionState(
        session_id=f"eval_{case.case_id}",
        ui_language="zh",
    )

    # Initial input
    response = run_pipeline(
        user_text=case.input_text,
        session=session,
        config=config,
        is_answer=False,
    )

    # If a question is asked, provide the answer for its slot (by slot name)
    guard = 0
    while response.get("response_type") == "question" and guard < 30:
        slot_id = response.get("slot")
        if not slot_id:
            break
        if slot_id in case.answers:
            answer = case.answers[slot_id]
        elif slot_id in CORE_SLOT_DEFAULTS:
            answer = CORE_SLOT_DEFAULTS[slot_id]
        else:
            break  # 该问题没有预设答案,停止追问
        response = run_pipeline(
            user_text="",
            session=session,
            config=config,
            is_answer=True,
            answer_value=answer,
        )
        guard += 1

    actual_level = response.get("level") or "UNKNOWN"

    expected_rank = SEVERITY_RANK.get(case.expected_level, 0)
    actual_rank = SEVERITY_RANK.get(actual_level, 0)

    correct = actual_level == case.expected_level
    is_under = actual_rank < expected_rank and not correct
    is_over = actual_rank > expected_rank and not correct

    return TestResult(
        case_id=case.case_id,
        expected_level=case.expected_level,
        actual_level=actual_level,
        correct=correct,
        is_under_triage=is_under,
        is_over_triage=is_over,
    )


def run_all_evals(cases_dir: Path | None = None) -> dict:
    """Run all evaluation cases."""
    if cases_dir is None:
        cases_dir = PROJECT_ROOT / "docs" / "content"

    config = load_config(PROJECT_ROOT / "contracts")

    all_cases = []
    all_results = []

    for cases_file in sorted(cases_dir.glob("cases_*.md")):
        module = cases_file.stem.replace("cases_", "")
        cases = parse_cases_file(cases_file)
        all_cases.extend(cases)
        print(f"\n=== {module} ({len(cases)} cases) ===")

        for case in cases:
            result = run_case(case, config)
            all_results.append(result)
            status = "✅" if result.correct else ("⚠️ UNDER" if result.is_under_triage else "❌ OVER")
            print(f"  {status} {result.case_id}: expected={result.expected_level}, actual={result.actual_level}")

    # Summary
    total = len(all_results)
    correct = sum(1 for r in all_results if r.correct)
    under = sum(1 for r in all_results if r.is_under_triage)
    over = sum(1 for r in all_results if r.is_over_triage)

    print(f"\n{'='*50}")
    print(f"Total: {total} | Correct: {correct} | Under-triage: {under} | Over-triage: {over}")
    if total > 0:
        print(f"Accuracy: {correct/total*100:.1f}%")
        print(f"Under-triage rate: {under/total*100:.1f}%")
        print(f"Over-triage rate: {over/total*100:.1f}%")

    return {
        "total": total,
        "correct": correct,
        "under_triage": under,
        "over_triage": over,
        "accuracy": correct / total if total > 0 else 0,
    }


if __name__ == "__main__":
    results = run_all_evals()
    sys.exit(0 if results["accuracy"] > 0.5 else 1)
