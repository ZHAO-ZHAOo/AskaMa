#!/usr/bin/env python3
"""AI Grandma — End-to-end demo script.

Runs simulated conversations through the full pipeline,
demonstrating all four triage levels.

Usage:
    python run_demo.py
"""

import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.orchestrator import SessionState, run_pipeline

# ── Colors ──
class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

LEVEL_EMOJI = {
    "EMERGENCY_NOW": "🚨",
    "SEE_DOCTOR_24_48H": "⏰",
    "BOOK_SOON": "📅",
    "SELF_CARE": "🏠",
}


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"{C.BOLD}  {title}{C.END}")
    print(f"{'='*60}")


def print_user(text: str):
    print(f"\n{C.CYAN}👤 User:{C.END} {text}")


def print_grandma(text: str, level: str | None = None):
    emoji = LEVEL_EMOJI.get(level, "👵") if level else "👵"
    badge = f" [{level}]" if level else ""
    print(f"{C.YELLOW}{emoji} Grandma{badge}:{C.END}")
    for line in text.split("\n"):
        print(f"  {line}")


def run_scenario(config, name: str, user_text: str, answers: list[tuple[str, str]] | None = None):
    """Run a full conversation scenario."""
    print_header(f"Scenario: {name}")

    session = SessionState(
        session_id=str(uuid.uuid4()),
        ui_language="zh",
    )

    print_user(user_text)

    response = run_pipeline(
        user_text=user_text,
        session=session,
        config=config,
        is_answer=False,
    )

    if response.get("response_type") == "question":
        print_grandma(response.get("text", ""))
        if response.get("options"):
            for i, opt in enumerate(response["options"]):
                print(f"    {i+1}. {opt.get('label', '')}")

        # Answer questions
        if answers:
            for ans_text, ans_value in answers:
                print_user(ans_text)
                response = run_pipeline(
                    user_text="",
                    session=session,
                    config=config,
                    is_answer=True,
                    answer_value=ans_value,
                )
                if response.get("response_type") == "question":
                    print_grandma(response.get("text", ""))
                    if response.get("options"):
                        for i, opt in enumerate(response["options"]):
                            print(f"    {i+1}. {opt.get('label', '')}")
                else:
                    print_grandma(response.get("text", ""), response.get("level"))
                    break
    else:
        print_grandma(response.get("text", ""), response.get("level"))


def main():
    # Load config
    config = load_config(PROJECT_ROOT / "contracts")

    print_header("AI Grandma — End-to-End Demo")
    print(f"  Modules: {', '.join(config.module_ids)}")
    print(f"  Red flag rules: {len(config.redflag_rules)}")
    print(f"  Question trees: {len(config.question_trees)}")
    print(f"  Decision tables: {len(config.decision_tables)}")
    print(f"  Self-care cards: {sum(len(v.get('cards',[])) for v in config.selfcare_cards.values())}")
    print(f"  Facilities: {len(config.facilities)}")

    # ── Scenario 1: EMERGENCY ──
    run_scenario(
        config,
        "🚨 Emergency — Heavy bleeding + fainting",
        "这个月经量特别大，浸透了裤子，还晕倒了",
    )

    # ── Scenario 2: EMERGENCY ──
    run_scenario(
        config,
        "🚨 Emergency — Sudden severe pain + fever",
        "突然肚子剧痛，10分，还发烧38.5度",
    )

    # ── Scenario 3: SEE_DOCTOR_24_48H ──
    run_scenario(
        config,
        "⏰ See Doctor — Severe period pain (8/10)",
        "痛经很厉害大概8分",
        answers=[
            ("8分", "8"),
            ("比平时严重", "worse_than_usual"),
            ("慢慢加重的", "gradual"),
            ("影响很大", "quite_a_lot"),
            ("没有头晕", "none"),
        ],
    )

    # ── Scenario 4: SELF_CARE ──
    run_scenario(
        config,
        "🏠 Self-care — Mild period pain (3/10)",
        "有点痛经大概3分",
        answers=[
            ("3分", "3"),
            ("和平常一样", "same_as_usual"),
            ("慢慢加重的", "gradual"),
            ("完全不影响", "not_at_all"),
            ("没有头晕", "none"),
        ],
    )

    # ── Scenario 5: BOOK_SOON ──
    run_scenario(
        config,
        "📅 Book Soon — Irregular bleeding (2 weeks)",
        "这次月经出血持续了两周还没停",
        answers=[
            ("没有经间出血", "false"),
            ("基本规律但偶尔不准", "somewhat_irregular"),
            ("没有异常分泌物", "false"),
            ("超过两周", "14"),
        ],
    )

    print_header("Demo Complete!")
    print(f"{C.GREEN}All scenarios executed successfully.{C.END}")
    print(f"\nTo start the web server:")
    print(f"  {C.BOLD}python -m uvicorn src.api.app:app --port 8000{C.END}")
    print(f"  Then open: {C.BOLD}http://localhost:8000{C.END}")


if __name__ == "__main__":
    main()
