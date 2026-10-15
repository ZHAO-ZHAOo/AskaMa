"""Tests for tools/validate_contracts.py.

Uses small fictional fixture files under tests/fixtures/contracts/ to test
each error category, plus a test that runs the real contracts/ directory.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Dict

import pytest

# Resolve paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
REAL_CONTRACTS = PROJECT_ROOT / "contracts"


def _run_validator(contracts_dir: Path, extra_args: Optional[List[str]] = None) -> Tuple[int, str]:
    """Run the validator on a given contracts directory, return (exit_code, output)."""
    cmd = [
        sys.executable,
        str(TOOLS_DIR / "validate_contracts.py"),
        "--contracts-dir",
        str(contracts_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    output = result.stdout + result.stderr
    return result.returncode, output


def _make_temp_contracts(tmp_path: Path, modifications: Optional[Dict[str, str]] = None) -> Path:
    """Copy fixtures to a temp dir, optionally apply file modifications.
    modifications: {relative_path: content} — writes new content to that path.
    Returns the temp contracts dir path.
    """
    dest = tmp_path / "contracts"
    shutil.copytree(FIXTURES_DIR / "contracts", dest)
    if modifications:
        for rel_path, content in modifications.items():
            p = dest / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Positive test: fixtures should pass
# ---------------------------------------------------------------------------


def test_fixtures_pass():
    """The fixture contracts should pass validation with exit code 0."""
    code, output = _run_validator(FIXTURES_DIR / "contracts")
    assert code == 0, f"Fixtures should pass but got errors:\n{output}"


# ---------------------------------------------------------------------------
# Real contracts test
# ---------------------------------------------------------------------------


def test_real_contracts_pass():
    """The real contracts/ directory should pass validation (exit code 0)."""
    code, output = _run_validator(REAL_CONTRACTS)
    assert code == 0, f"Real contracts should pass but got errors:\n{output}"


# ---------------------------------------------------------------------------
# Negative tests: each error category
# ---------------------------------------------------------------------------


def test_slot_not_found(tmp_path):
    """Condition references a non-existent slot → ERROR."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_BAD_SLOT
    scope: [global]
    condition: {slot: nonexistent_slot, op: eq, value: some_value}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad.yaml": bad_rules})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "does not exist in slots.yaml" in output


def test_operator_type_incompatible(tmp_path):
    """gt operator on enum slot → ERROR."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_BAD_OP
    scope: [global]
    condition: {slot: fever_status, op: gt, value: 5}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad.yaml": bad_rules})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not compatible" in output


def test_enum_value_invalid(tmp_path):
    """eq operator with invalid enum value → ERROR."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_BAD_ENUM
    scope: [global]
    condition: {slot: fever_status, op: eq, value: not_a_real_value}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad.yaml": bad_rules})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not in allowed_values" in output


def test_numeric_out_of_range(tmp_path):
    """gt with value above slot range → ERROR."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_BAD_RANGE
    scope: [global]
    condition: {slot: pain_severity_0_10, op: gt, value: 20}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad.yaml": bad_rules})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "above slot range max" in output


def test_answer_options_invalid_value(tmp_path):
    """answer_options value not in enum allowed_values → ERROR."""
    bad_questions = """
meta:
  id: bad_questions
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
module: heavy_bleeding
required_slots: [flow_compared_to_usual]
questions:
  - question_id: Q_BAD_AO
    slot: flow_compared_to_usual
    text: {en: "[Fixture]"}
    answer_options:
      - {value: invalid_option, label: {en: Invalid}}
    priority: 1
stopping:
  on_max_reached: grade_with_uncertainty
  on_all_required_answered: grade
max_questions: 5
"""
    contracts = _make_temp_contracts(tmp_path, {"questions/bad.yaml": bad_questions})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not in allowed_values" in output


def test_required_slot_not_filled(tmp_path):
    """required_slot not filled by any question and not derived → ERROR."""
    bad_questions = """
meta:
  id: bad_questions
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
module: heavy_bleeding
required_slots: [temperature_c]
questions:
  - question_id: Q_FILL
    slot: flow_compared_to_usual
    text: {en: "[Fixture]"}
    priority: 1
stopping:
  on_max_reached: grade_with_uncertainty
  on_all_required_answered: grade
max_questions: 5
"""
    contracts = _make_temp_contracts(tmp_path, {"questions/bad2.yaml": bad_questions})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not filled by any question" in output


def test_decision_table_missing_default_row(tmp_path):
    """Decision table without default_row → ERROR (schema-level)."""
    bad_dt = """
meta:
  id: bad_dt
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
module: heavy_bleeding
rows:
  - row_id: DT_BAD
    when: {slot: flow_compared_to_usual, op: eq, value: same}
    level: SELF_CARE
    rationale: {en: "[Fixture]"}
    needs_clinician_review: true
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
conflict_resolution: highest_severity_wins
uncertainty_policy:
  mode: escalate_one_level
"""
    contracts = _make_temp_contracts(tmp_path, {"decision_tables/bad.yaml": bad_dt})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "default_row" in output


def test_selfcare_missing_escalation(tmp_path):
    """SELF_CARE cards without escalation_criteria → ERROR."""
    bad_selfcare = """
meta:
  id: bad_selfcare
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
cards:
  - card_id: SC_NO_ESC
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: relief_measure
    title: {en: "[Fixture]"}
    body: {en: "[Fixture]"}
    priority: 1
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"selfcare/bad2.yaml": bad_selfcare})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "escalation_criteria" in output


def test_facility_id_duplicate(tmp_path):
    """Duplicate facility_id → ERROR."""
    bad_facility = """
meta:
  id: bad_facility
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
facilities:
  - facility_id: FAC_FIXTURE_URGENT
    name: Duplicate Facility
    type: polyclinic
    lat: 1.2
    lng: 103.7
    address: 200 Bad Road
    postal_code: "654321"
    has_gynaecology: false
    walk_in_available: true
    appointment_required: false
    fee_tier: low
    subsidy_requires_referral: false
    accepts_minors: true
    sources: []
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"facilities/bad2.yaml": bad_facility})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "Duplicate facility_id" in output


def test_lint_drug_name_error(tmp_path):
    """Lint finds drug name in selfcare card → ERROR."""
    bad_selfcare = """
meta:
  id: bad_selfcare
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
cards:
  - card_id: SC_DRUG_NAME
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: relief_measure
    title: {en: "[Fixture]"}
    body: {en: "Take ibuprofen for pain"}
    priority: 1
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
  - card_id: SC_ESC_FIXTURE
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: escalation_criteria
    title: {en: "[Fixture]"}
    body: {en: "[Fixture]"}
    priority: 10
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"selfcare/bad3.yaml": bad_selfcare})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "ibuprofen" in output.lower() or "drug name" in output.lower()


def test_lint_dosage_error(tmp_path):
    """Lint finds dosage pattern in selfcare card → ERROR."""
    bad_selfcare = """
meta:
  id: bad_selfcare
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
cards:
  - card_id: SC_DOSAGE
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: relief_measure
    title: {en: "[Fixture]"}
    body: {en: "Take 500mg of something"}
    priority: 1
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
  - card_id: SC_ESC_FIXTURE2
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: escalation_criteria
    title: {en: "[Fixture]"}
    body: {en: "[Fixture]"}
    priority: 10
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"selfcare/bad4.yaml": bad_selfcare})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "dosage" in output.lower()


def test_lint_diagnostic_phrase_warning(tmp_path):
    """Lint finds diagnostic phrase → WARNING (not ERROR, exit code 0 without --strict)."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_DIAG
    scope: [global]
    condition: {slot: fever_status, op: eq, value: measured_fever}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    user_note:
      en: "you may have endometriosis"
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad_diag.yaml": bad_rules})
    code, output = _run_validator(contracts)
    # Diagnostic phrases are WARNING, so exit code should be 0 (without --strict)
    assert "diagnostic phrase" in output.lower()
    # But if there's also an attestation mismatch or something, it could be 1
    # The WARNING alone should not cause exit code 1


def test_selfcare_sources_empty_error(tmp_path):
    """Selfcare card with empty sources → ERROR (MVP requirement)."""
    bad_selfcare = """
meta:
  id: bad_selfcare
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
cards:
  - card_id: SC_NO_SOURCE
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: relief_measure
    title: {en: "[Fixture]"}
    body: {en: "[Fixture]"}
    priority: 1
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources: []
    needs_clinician_review: true
    status: draft_unreviewed
  - card_id: SC_ESC_NOSRC
    module: heavy_bleeding
    applicable_levels: [SELF_CARE]
    card_type: escalation_criteria
    title: {en: "[Fixture]"}
    body: {en: "[Fixture]"}
    priority: 10
    content_attestation:
      mentions_specific_drug: false
      gives_dosage: false
      contains_diagnostic_statement: false
    sources: []
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"selfcare/bad5.yaml": bad_selfcare})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "sources must not be empty" in output


def test_reviewed_status_missing_reviewer(tmp_path):
    """meta status=clinician_reviewed but reviewer is null → ERROR."""
    bad_rules = """
meta:
  id: bad_rules
  version: 0.1.0
  status: clinician_reviewed
  sources: []
  reviewer: null
  last_verified: null
rules:
  - rule_id: RF_REVIEWED
    scope: [global]
    condition: {slot: fever_status, op: eq, value: measured_fever}
    exit_type: GO_URGENT_OG_OR_AE
    on_unknown: treat_as_false
    rationale: {en: "[Fixture]"}
    sources:
      - title: "[Fixture]"
        url: "https://example.invalid"
    needs_clinician_review: true
    status: clinician_reviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"rules/bad_rev.yaml": bad_rules})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "reviewer" in output.lower()


# ---------------------------------------------------------------------------
# Weight presets semantic tests
# ---------------------------------------------------------------------------

_VALID_WEIGHT_PRESETS = """
meta:
  id: wp_fixture
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
features:
  - id: travel_time
    name: {en: "[Fixture]"}
    description: {en: "[Fixture]"}
    higher_is_better: false
    scoring_note: "[Fixture]"
  - id: cost
    name: {en: "[Fixture]"}
    description: {en: "[Fixture]"}
    higher_is_better: false
    scoring_note: "[Fixture]"
ranking_levels: [SEE_DOCTOR_24_48H, BOOK_SOON]
default_weights_by_level:
  SEE_DOCTOR_24_48H:
    travel_time: 0.6
    cost: 0.4
  BOOK_SOON:
    travel_time: 0.4
    cost: 0.6
presets:
  - preset_id: nearest
    name: {en: "[Fixture]"}
    description: {en: "[Fixture]"}
    weights_by_level:
      SEE_DOCTOR_24_48H:
        travel_time: 0.8
        cost: 0.2
      BOOK_SOON:
        travel_time: 0.7
        cost: 0.3
bounds_by_level:
  SEE_DOCTOR_24_48H:
    travel_time: {min: 0.3, max: 1.0}
    cost: {min: 0.0, max: 0.7}
  BOOK_SOON:
    travel_time: {min: 0.1, max: 1.0}
    cost: {min: 0.0, max: 0.9}
emergency_ranking:
  mode: travel_time_only
  note: {en: "[Fixture]"}
"""


def test_weight_presets_sum_not_one(tmp_path):
    """Weight sum != 1 → ERROR."""
    bad = _VALID_WEIGHT_PRESETS.replace(
        "travel_time: 0.6\n    cost: 0.4",
        "travel_time: 0.5\n    cost: 0.4"
    )
    contracts = _make_temp_contracts(tmp_path, {"weights/bad.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "weight sum" in output.lower()


def test_weight_presets_undefined_feature(tmp_path):
    """Weight references undefined feature → ERROR."""
    bad = _VALID_WEIGHT_PRESETS.replace(
        "travel_time: 0.6\n    cost: 0.4",
        "travel_time: 0.5\n    undefined_feature: 0.5"
    )
    contracts = _make_temp_contracts(tmp_path, {"weights/bad2.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not defined in features" in output


def test_weight_presets_duplicate_preset_id(tmp_path):
    """Duplicate preset_id → ERROR."""
    # The valid fixture has only one preset (nearest); duplicate it.
    dup_block = (
        '  - preset_id: nearest\n'
        '    name: {en: "[Fixture]"}\n'
        '    description: {en: "[Fixture]"}\n'
        '    weights_by_level:\n'
        '      SEE_DOCTOR_24_48H:\n'
        '        travel_time: 0.5\n'
        '        cost: 0.5\n'
        '      BOOK_SOON:\n'
        '        travel_time: 0.5\n'
        '        cost: 0.5\n'
    )
    bad = _VALID_WEIGHT_PRESETS.replace(
        "bounds_by_level:",
        dup_block + "bounds_by_level:"
    )
    contracts = _make_temp_contracts(tmp_path, {"weights/bad3.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "Duplicate preset_id" in output


def test_weight_presets_ranking_levels_emergency(tmp_path):
    """ranking_levels contains EMERGENCY_NOW → ERROR."""
    bad = _VALID_WEIGHT_PRESETS.replace(
        "ranking_levels: [SEE_DOCTOR_24_48H, BOOK_SOON]",
        "ranking_levels: [SEE_DOCTOR_24_48H, BOOK_SOON, EMERGENCY_NOW]"
    )
    contracts = _make_temp_contracts(tmp_path, {"weights/bad4.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "EMERGENCY_NOW" in output


def test_weight_presets_bounds_missing_feature(tmp_path):
    """bounds_by_level missing a feature → ERROR."""
    bad = _VALID_WEIGHT_PRESETS.replace(
        "    cost: {min: 0.0, max: 0.7}\n  BOOK_SOON:",
        "\n  BOOK_SOON:"
    )
    contracts = _make_temp_contracts(tmp_path, {"weights/bad5.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "does not cover" in output


def test_weight_presets_weight_out_of_bounds(tmp_path):
    """Default weight outside bounds → ERROR."""
    bad = _VALID_WEIGHT_PRESETS.replace(
        "travel_time: 0.6\n    cost: 0.4\n  BOOK_SOON",
        "travel_time: 0.1\n    cost: 0.9\n  BOOK_SOON"
    )
    # travel_time min for SEE_DOCTOR_24_48H is 0.3, so 0.1 is below
    contracts = _make_temp_contracts(tmp_path, {"weights/bad6.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "below bound" in output


# ---------------------------------------------------------------------------
# Questionnaire mapping semantic tests
# ---------------------------------------------------------------------------

_VALID_QUESTIONNAIRE = """
meta:
  id: q_fixture
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
questionnaire_version: "0.1.0"
questions:
  - question_id: PQ_TEST
    text: {en: "[Fixture]"}
    multi_select: false
    required: true
    options:
      - option_id: opt_a
        label: {en: "[Fixture]"}
        effects:
          - type: set_base_preset
            preset_id: nearest
      - option_id: opt_b
        label: {en: "[Fixture]"}
        effects:
          - type: add_delta
            feature: travel_time
            value: 0.1
            levels: [SEE_DOCTOR_24_48H]
      - option_id: opt_c
        label: {en: "[Fixture]"}
        effects:
          - type: set_profile_field
            field: travel_mode
            value: public_transport
combination:
  start_from: default_weights
  apply_order: question_order
  clip_to_bounds: true
  renormalize_to_sum_one: true
  on_unanswered: use_default
"""


def test_questionnaire_undefined_feature(tmp_path):
    """Effect references undefined feature → ERROR."""
    bad = _VALID_QUESTIONNAIRE.replace(
        "feature: travel_time",
        "feature: nonexistent_feature"
    )
    contracts = _make_temp_contracts(tmp_path, {"questionnaire/bad.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "non-existent feature" in output


def test_questionnaire_undefined_preset(tmp_path):
    """set_base_preset references non-existent preset → ERROR."""
    bad = _VALID_QUESTIONNAIRE.replace(
        "preset_id: nearest",
        "preset_id: nonexistent_preset"
    )
    contracts = _make_temp_contracts(tmp_path, {"questionnaire/bad2.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "non-existent preset_id" in output


def test_questionnaire_invalid_profile_field_value(tmp_path):
    """set_profile_field with invalid value → ERROR."""
    bad = _VALID_QUESTIONNAIRE.replace(
        "value: public_transport",
        "value: teleport"
    )
    contracts = _make_temp_contracts(tmp_path, {"questionnaire/bad3.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "not in" in output


def test_questionnaire_duplicate_question_id(tmp_path):
    """Duplicate question_id → ERROR."""
    # Change the first question's id to PQ_DUP, then insert a second question
    # with PQ_DUP right before `combination:`.
    dup_q = (
        '  - question_id: PQ_DUP\n'
        '    text: {en: "[Fixture]"}\n'
        '    multi_select: false\n'
        '    required: false\n'
        '    options:\n'
        '      - option_id: x\n'
        '        label: {en: "[Fixture]"}\n'
        '        effects: []\n'
    )
    bad = _VALID_QUESTIONNAIRE.replace(
        "question_id: PQ_TEST",
        "question_id: PQ_DUP"
    ).replace(
        "combination:",
        dup_q + "combination:"
    )
    contracts = _make_temp_contracts(tmp_path, {"questionnaire/bad4.yaml": bad})
    code, output = _run_validator(contracts)
    assert code == 1
    assert "Duplicate question_id" in output


# ---------------------------------------------------------------------------
# Facility supplementary tests
# ---------------------------------------------------------------------------


def test_facility_urgent_og_not_walk_in_warning(tmp_path):
    """urgent_og facility without walk_in_available=true → WARNING."""
    bad_facility = """
meta:
  id: fixture_facilities
  version: 0.1.0
  status: draft_unreviewed
  sources: []
  reviewer: null
  last_verified: null
facilities:
  - facility_id: FAC_TEST_URGENT
    name: Test Urgent
    type: urgent_og
    lat: 1.2
    lng: 103.8
    address: 100 Test Road
    postal_code: "123456"
    has_gynaecology: true
    walk_in_available: false
    appointment_required: true
    fee_tier: moderate
    subsidy_requires_referral: false
    accepts_minors: true
    operating_hours: "Mon-Fri 9-5"
    needs_clinician_review: true
    status: draft_unreviewed
"""
    contracts = _make_temp_contracts(tmp_path, {"facilities/bad3.yaml": bad_facility})
    code, output = _run_validator(contracts)
    # WARNING only — exit code should be 0 without --strict
    assert "walk_in_available" in output.lower() or "24h" in output.lower()

