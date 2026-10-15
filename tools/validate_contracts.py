#!/usr/bin/env python3
"""AI Grandma contract validator.

Validates all contract files under a contracts directory:
  - JSON Schema validation (with $ref resolution and format checking)
  - Cross-file semantic checks (slot references, enum values, operator compatibility, etc.)
  - Content safety lint (drug names, dosage patterns, diagnostic phrases)

Usage:
  python tools/validate_contracts.py [--contracts-dir contracts] [--strict]

Exit code 0 = no ERRORs (WARNING/INFO allowed).
Exit code 1 = at least one ERROR (or WARNING with --strict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_DIR_NAME = "schemas"
EXAMPLES_DIR_NAME = "examples"

EXPECTED_LEVEL_IDS = {"EMERGENCY_NOW", "SEE_DOCTOR_24_48H", "BOOK_SOON", "SELF_CARE"}
EXPECTED_LEVEL_COUNT = 4
EXPECTED_MODULE_IDS = {
    "heavy_bleeding",
    "severe_period_pain",
    "late_or_missed_period",
    "irregular_or_intermenstrual_bleeding",
}
EXPECTED_MODULE_COUNT = 4

VALID_SLOT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VALID_USED_BY = {"l1_redflag", "l2_grading", "l3_selfcare", "l4_recommend", "logging"}
VALID_STATUSES = {"draft_unreviewed", "clinician_reviewed", "approved"}

VALID_DURATION_UNITS = {"hours", "days", "weeks"}
SCALAR_TYPES = {"int", "float", "bool", "string", "date", "text", "duration"}

CONTENT_DIRS = {
    "rules": "redflag_rules",
    "questions": "question_tree",
    "decision_tables": "decision_table",
    "selfcare": "selfcare_card",
    "facilities": "facility",
    "weights": "weight_presets",
    "questionnaire": "questionnaire_mapping",
}

LINT_FILE = "tools/lint_denylist.yaml"

# Subdirectories whose files should be checked for non-empty sources (MVP rule)
SOURCE_CHECK_DIRS = {"rules", "decision_tables", "selfcare"}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "ERROR" or "WARNING" or "INFO"
    file: str
    location: str  # JSON-path-like, e.g. "rules[2].condition.all_of[0]"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.file}:{self.location} — {self.message}"


@dataclass
class SlotInfo:
    sid: str
    slot_type: str
    allowed_values: list[Any]  # list of ids (for enum) or empty
    multi: bool
    range: dict | None
    derived: bool
    derivation_note: str | None
    module_tags: list[str]
    used_by: list[str]
    status: str


@dataclass
class LoadedFile:
    rel_path: str  # relative to contracts dir
    data: Any
    schema_name: str | None  # None for levels/modules/slots
    is_example: bool


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)
    status_counts: dict[str, int] = field(default_factory=dict)  # status -> count

    def add(self, severity: str, file: str, location: str, message: str) -> None:
        self.issues.append(Issue(severity, file, location, message))

    def error(self, file: str, location: str, message: str) -> None:
        self.add("ERROR", file, location, message)

    def warning(self, file: str, location: str, message: str) -> None:
        self.add("WARNING", file, location, message)

    def info(self, file: str, location: str, message: str) -> None:
        self.add("INFO", file, location, message)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "ERROR" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "WARNING" for i in self.issues)

    def grouped_output(self) -> str:
        lines: list[str] = []
        by_file: dict[str, list[Issue]] = {}
        for issue in self.issues:
            by_file.setdefault(issue.file, []).append(issue)
        for f in sorted(by_file):
            lines.append(f"--- {f} ---")
            for issue in by_file[f]:
                lines.append(f"  {issue}")
            lines.append("")
        return "\n".join(lines)

    def summary(self) -> str:
        errors = sum(1 for i in self.issues if i.severity == "ERROR")
        warnings = sum(1 for i in self.issues if i.severity == "WARNING")
        infos = sum(1 for i in self.issues if i.severity == "INFO")
        lines = [
            f"Summary: {errors} ERROR(s), {warnings} WARNING(s), {infos} INFO(s)",
        ]
        if self.status_counts:
            lines.append("Content status breakdown:")
            for s in ["draft_unreviewed", "clinician_reviewed", "approved"]:
                cnt = self.status_counts.get(s, 0)
                if cnt:
                    lines.append(f"  {s}: {cnt}")
        lines.append(
            "INFO: 以下内容尚未经过临床审核（MVP 阶段如实标注，正式上线前需临床医生审核）。"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _yaml_load(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_schemas(contracts_dir: Path) -> dict[str, dict]:
    schema_dir = contracts_dir / SCHEMA_DIR_NAME
    schemas: dict[str, dict] = {}
    for p in sorted(schema_dir.glob("*.schema.json")):
        # p.stem for "decision_table.schema.json" is "decision_table.schema"
        # We want the key to be "decision_table" (strip .schema suffix)
        key = p.name.replace(".schema.json", "")
        with open(p, encoding="utf-8") as f:
            schemas[key] = json.load(f)
    # Also load interface schemas from the interfaces/ subdirectory
    interfaces_dir = schema_dir / "interfaces"
    if interfaces_dir.is_dir():
        for p in sorted(interfaces_dir.glob("*.schema.json")):
            key = p.name.replace(".schema.json", "")
            with open(p, encoding="utf-8") as f:
                schemas[key] = json.load(f)
    return schemas


def _build_registry(schemas: dict[str, dict]) -> Registry:
    registry = Registry()
    for name, schema in schemas.items():
        uri = schema.get("$id", f"https://ai-grandma/schemas/{name}.schema.json")
        registry = registry.with_resource(uri, Resource.from_contents(schema))
    return registry


def _load_content_files(contracts_dir: Path) -> list[LoadedFile]:
    """Load all YAML files from content dirs (rules, questions, etc.) and examples."""
    files: list[LoadedFile] = []
    for dir_name, schema_name in CONTENT_DIRS.items():
        d = contracts_dir / dir_name
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.yaml")):
            data = _yaml_load(p)
            files.append(
                LoadedFile(
                    rel_path=str(p.relative_to(contracts_dir)),
                    data=data,
                    schema_name=schema_name,
                    is_example=False,
                )
            )
    return files


def _load_example_files(contracts_dir: Path) -> list[LoadedFile]:
    """Load example YAML files, mapping them to the correct schema by filename prefix."""
    ex_dir = contracts_dir / EXAMPLES_DIR_NAME
    files: list[LoadedFile] = []
    if not ex_dir.is_dir():
        return files
    # All schema names that can have example files (content + interface + events)
    all_schema_names = list(CONTENT_DIRS.values()) + [
        "user_profile",
        "weight_presets",
        "questionnaire_mapping",
        "session_state",
        "intake_result",
        "redflag_result",
        "grading_result",
        "selfcare_output",
        "recommendation_request",
        "ranked_places",
        "final_response",
        "events",
    ]
    for p in sorted(ex_dir.glob("*.yaml")):
        stem = p.stem  # e.g. redflag_rules.valid, redflag_rules.invalid_missing_en
        # Special handling for events files (prefix "events")
        # Check longest prefixes first to avoid partial matches
        matched = False
        for prefix in sorted(all_schema_names, key=len, reverse=True):
            if stem.startswith(prefix + "."):
                data = _yaml_load(p)
                files.append(
                    LoadedFile(
                        rel_path=str(p.relative_to(contracts_dir)),
                        data=data,
                        schema_name=prefix,
                        is_example=True,
                    )
                )
                matched = True
                break
    return files


def _load_slots(contracts_dir: Path) -> dict[str, SlotInfo]:
    path = contracts_dir / "slots.yaml"
    raw = _yaml_load(path)
    slots: dict[str, SlotInfo] = {}
    if not raw or "slots" not in raw:
        return slots
    for entry in raw["slots"]:
        sid = entry["id"]
        slot_type = entry["type"]
        allowed = []
        if slot_type == "enum" and entry.get("allowed_values"):
            for av in entry["allowed_values"]:
                if isinstance(av, dict):
                    allowed.append(av.get("id"))
        slots[sid] = SlotInfo(
            sid=sid,
            slot_type=slot_type,
            allowed_values=allowed,
            multi=entry.get("multi", False),
            range=entry.get("range"),
            derived=entry.get("derived", False),
            derivation_note=entry.get("derivation_note"),
            module_tags=entry.get("module_tags", []),
            used_by=entry.get("used_by", []),
            status=entry.get("status", "draft_unreviewed"),
        )
    return slots


# ---------------------------------------------------------------------------
# Batch 1: Schema validation
# ---------------------------------------------------------------------------


def validate_schema(
    result: ValidationResult,
    files: list[LoadedFile],
    schemas: dict[str, dict],
    registry: Registry,
) -> None:
    fc = FormatChecker()
    for lf in files:
        if lf.schema_name is None or lf.schema_name not in schemas:
            result.error(lf.rel_path, "", f"No schema found for {lf.rel_path}")
            continue
        schema = schemas[lf.schema_name]
        validator = Draft202012Validator(schema, registry=registry, format_checker=fc)
        errors = list(validator.iter_errors(lf.data))
        # For invalid examples, schema failure is expected — skip reporting.
        # check_examples handles validating that they fail as expected.
        if lf.is_example and (".invalid" in lf.rel_path or "/invalid" in lf.rel_path):
            # Track status counts but don't report schema errors (expected to fail)
            _track_item_statuses(result, lf)
            continue
        for e in errors:
            loc = e.json_path if e.json_path else "$"
            result.error(lf.rel_path, loc, e.message)
        # Track status counts
        meta = lf.data.get("meta") if isinstance(lf.data, dict) else None
        if meta and isinstance(meta, dict):
            st = meta.get("status")
            if st:
                result.status_counts[st] = result.status_counts.get(st, 0) + 1
        # Also track per-item statuses
        _track_item_statuses(result, lf)


def _track_item_statuses(result: ValidationResult, lf: LoadedFile) -> None:
    data = lf.data
    if not isinstance(data, dict):
        return
    if "rules" in data and isinstance(data["rules"], list):
        for r in data["rules"]:
            st = r.get("status")
            if st:
                result.status_counts[st] = result.status_counts.get(st, 0) + 1
    if "cards" in data and isinstance(data["cards"], list):
        for c in data["cards"]:
            st = c.get("status")
            if st:
                result.status_counts[st] = result.status_counts.get(st, 0) + 1
    if "facilities" in data and isinstance(data["facilities"], list):
        for f in data["facilities"]:
            st = f.get("status")
            if st:
                result.status_counts[st] = result.status_counts.get(st, 0) + 1


# ---------------------------------------------------------------------------
# Batch 2: Dictionary checks (levels, modules, slots)
# ---------------------------------------------------------------------------


def check_levels(result: ValidationResult, contracts_dir: Path) -> None:
    path = contracts_dir / "levels.yaml"
    if not path.exists():
        result.error("levels.yaml", "", "File not found")
        return
    data = _yaml_load(path)
    if not data:
        result.error("levels.yaml", "", "Empty or invalid YAML")
        return

    levels = data.get("levels", [])
    if len(levels) != EXPECTED_LEVEL_COUNT:
        result.error("levels.yaml", "levels", f"Expected {EXPECTED_LEVEL_COUNT} levels, got {len(levels)}")

    ids = set()
    ranks = set()
    for lv in levels:
        lid = lv.get("id")
        ids.add(lid)
        sr = lv.get("severity_rank")
        ranks.add(sr)
    if ids != EXPECTED_LEVEL_IDS:
        result.error("levels.yaml", "levels", f"Level ids mismatch: {ids} != {EXPECTED_LEVEL_IDS}")
    if len(ranks) != EXPECTED_LEVEL_COUNT:
        result.error("levels.yaml", "levels", f"Severity ranks not unique: {ranks}")

    esc_order = data.get("escalation_rule", {}).get("order", [])
    if set(esc_order) != EXPECTED_LEVEL_IDS:
        result.error("levels.yaml", "escalation_rule.order", f"Escalation order does not cover all levels: {esc_order}")

    _check_meta(result, "levels.yaml", data.get("meta"))


def check_modules(result: ValidationResult, contracts_dir: Path) -> None:
    path = contracts_dir / "modules.yaml"
    if not path.exists():
        result.error("modules.yaml", "", "File not found")
        return
    data = _yaml_load(path)
    if not data:
        result.error("modules.yaml", "", "Empty or invalid YAML")
        return

    modules = data.get("modules", [])
    if len(modules) != EXPECTED_MODULE_COUNT:
        result.error("modules.yaml", "modules", f"Expected {EXPECTED_MODULE_COUNT} modules, got {len(modules)}")

    ids = {m.get("id") for m in modules}
    if ids != EXPECTED_MODULE_IDS:
        result.error("modules.yaml", "modules", f"Module ids mismatch: {ids} != {EXPECTED_MODULE_IDS}")

    _check_meta(result, "modules.yaml", data.get("meta"))


def _normalize_allowed_ids(av_list: Any) -> list[Any]:
    """Normalize allowed_values ids, mapping YAML 1.1 booleans back to strings."""
    if not av_list:
        return []
    result = []
    for av in av_list:
        if not isinstance(av, dict):
            continue
        raw_id = av.get("id")
        if raw_id is True:
            raw_id = "yes"
        elif raw_id is False:
            raw_id = "no"
        result.append(raw_id)
    return result


def check_slots(result: ValidationResult, contracts_dir: Path) -> dict[str, SlotInfo]:
    path = contracts_dir / "slots.yaml"
    if not path.exists():
        result.error("slots.yaml", "", "File not found")
        return {}
    data = _yaml_load(path)
    if not data:
        result.error("slots.yaml", "", "Empty or invalid YAML")
        return {}

    slots_list = data.get("slots", [])
    slots: dict[str, SlotInfo] = {}
    seen_ids: set[str] = set()

    for i, entry in enumerate(slots_list):
        sid = entry.get("id")
        loc = f"slots[{i}].{sid or i}"

        if sid is None:
            result.error("slots.yaml", f"slots[{i}]", "Missing id")
            continue

        if sid in seen_ids:
            result.error("slots.yaml", loc, f"Duplicate slot id: {sid}")
        seen_ids.add(sid)

        if not VALID_SLOT_ID_RE.match(sid):
            result.error("slots.yaml", loc, f"Slot id does not match ^[a-z][a-z0-9_]*$: {sid}")

        slot_type = entry.get("type")
        # enum checks
        if slot_type == "enum":
            av = entry.get("allowed_values")
            if not av:
                result.error("slots.yaml", loc, "enum slot must have non-empty allowed_values")
            else:
                for j, item in enumerate(av):
                    if not isinstance(item, dict):
                        result.error("slots.yaml", f"{loc}.allowed_values[{j}]", "Must be an object")
                        continue
                    raw_id = item.get("id")
                    # YAML 1.1 (pyyaml) treats bare yes/no/on/off as booleans.
                    # Map them back to string ids for enum value tracking.
                    if raw_id is True:
                        raw_id = "yes"
                    elif raw_id is False:
                        raw_id = "no"
                    if raw_id is None:
                        result.error("slots.yaml", f"{loc}.allowed_values[{j}]", "Missing id")
                    label = item.get("label")
                    # YAML 1.1 treats bare Yes/No as booleans; map back to string
                    en_val = label.get("en") if isinstance(label, dict) else None
                    if en_val is True:
                        en_val = "yes"
                    elif en_val is False:
                        en_val = "no"
                    if not isinstance(label, dict) or not en_val:
                        result.error("slots.yaml", f"{loc}.allowed_values[{j}].label", "Missing en label")
        else:
            av = entry.get("allowed_values")
            if av:
                result.error("slots.yaml", loc, f"Non-enum slot should have null allowed_values, got: {av}")

        # module_tags
        mt = entry.get("module_tags", [])
        for tag in mt:
            if tag != "global" and tag not in EXPECTED_MODULE_IDS:
                result.error("slots.yaml", loc, f"module_tags contains unknown value: {tag}")

        # used_by
        ub = entry.get("used_by", [])
        if not ub:
            result.error("slots.yaml", loc, "used_by must be non-empty")
        for u in ub:
            if u not in VALID_USED_BY:
                result.error("slots.yaml", loc, f"used_by contains unknown value: {u}")

        # derived
        if entry.get("derived"):
            if not entry.get("derivation_note"):
                result.error("slots.yaml", loc, "derived: true requires derivation_note")

        # range checks for int/float
        if slot_type in ("int", "float"):
            rng = entry.get("range")
            if rng is not None:
                if not isinstance(rng, dict):
                    result.error("slots.yaml", loc, "range must be an object")
                else:
                    rmin = rng.get("min")
                    rmax = rng.get("max")
                    if rmin is not None and rmax is not None and rmin > rmax:
                        result.error("slots.yaml", loc, f"range min ({rmin}) > max ({rmax})")

        # i18n text checks
        for field in ("description",):
            val = entry.get(field)
            if isinstance(val, dict) and not val.get("en"):
                result.error("slots.yaml", loc, f"{field}.en is empty or missing")

        # No _zh/_en suffix keys
        _check_no_legacy_keys(result, "slots.yaml", loc, entry)

        # status
        st = entry.get("status")
        if st not in VALID_STATUSES:
            result.error("slots.yaml", loc, f"Invalid status: {st}")

        slots[sid] = SlotInfo(
            sid=sid,
            slot_type=slot_type,
            allowed_values=_normalize_allowed_ids(entry.get("allowed_values")) if slot_type == "enum" else [],
            multi=entry.get("multi", False),
            range=entry.get("range"),
            derived=entry.get("derived", False),
            derivation_note=entry.get("derivation_note"),
            module_tags=entry.get("module_tags", []),
            used_by=entry.get("used_by", []),
            status=st or "draft_unreviewed",
        )

    _check_meta(result, "slots.yaml", data.get("meta"))
    return slots


def _check_no_legacy_keys(result: ValidationResult, file: str, loc: str, obj: Any) -> None:
    """Check for _zh/_en suffix keys that should have been migrated to i18n_text."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_zh") or k.endswith("_en"):
                result.error(file, f"{loc}.{k}", f"Legacy key '{k}' should use i18n_text object instead")
            _check_no_legacy_keys(result, file, f"{loc}.{k}", v)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_no_legacy_keys(result, file, f"{loc}[{i}]", item)


def _check_meta(result: ValidationResult, file: str, meta: Any) -> None:
    """Check meta block for reviewed/approved status requirements."""
    if not isinstance(meta, dict):
        result.error(file, "meta", "Missing or invalid meta")
        return

    st = meta.get("status")
    if st in ("clinician_reviewed", "approved"):
        reviewer = meta.get("reviewer")
        last_verified = meta.get("last_verified")
        if not reviewer:
            result.error(file, "meta.reviewer", f"status={st} but reviewer is empty")
        if not last_verified:
            result.error(file, "meta.last_verified", f"status={st} but last_verified is empty")


# ---------------------------------------------------------------------------
# Batch 3: Semantic cross-checks
# ---------------------------------------------------------------------------


def check_condition(
    result: ValidationResult,
    file: str,
    loc: str,
    cond: Any,
    slots: dict[str, SlotInfo],
) -> None:
    """Recursively check a condition expression for slot validity and operator compatibility."""
    if not isinstance(cond, dict):
        return

    if "all_of" in cond:
        for i, sub in enumerate(cond["all_of"]):
            check_condition(result, file, f"{loc}.all_of[{i}]", sub, slots)
    elif "any_of" in cond:
        for i, sub in enumerate(cond["any_of"]):
            check_condition(result, file, f"{loc}.any_of[{i}]", sub, slots)
    elif "not" in cond:
        check_condition(result, file, f"{loc}.not", cond["not"], slots)
    else:
        # It's a predicate
        sid = cond.get("slot")
        op = cond.get("op")
        val = cond.get("value")

        if sid is None or op is None:
            result.error(file, loc, f"Predicate missing slot or op: {cond}")
            return

        slot = slots.get(sid)
        if slot is None:
            result.error(file, loc, f"Slot '{sid}' does not exist in slots.yaml")
            return

        # Derived slot info
        if slot.derived:
            result.info(file, loc, f"Slot '{sid}' is derived; confirm calculation logic is implemented")

        # Operator compatibility
        st = slot.slot_type

        if op in ("gt", "gte", "lt", "lte"):
            if st not in ("int", "float", "duration", "date"):
                result.error(file, loc, f"op '{op}' not compatible with slot type '{st}' (slot '{sid}')")
            else:
                if st == "duration" and isinstance(val, dict):
                    unit = val.get("unit")
                    if unit not in VALID_DURATION_UNITS:
                        result.error(file, loc, f"duration unit '{unit}' not in {VALID_DURATION_UNITS}")
                if st == "date" and isinstance(val, str):
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                        result.error(file, loc, f"date comparison value '{val}' is not YYYY-MM-DD")
                if st in ("int", "float") and isinstance(val, (int, float)):
                    if slot.range:
                        rmin = slot.range.get("min")
                        rmax = slot.range.get("max")
                        if rmin is not None and val < rmin:
                            result.error(file, loc, f"value {val} below slot range min {rmin}")
                        if rmax is not None and val > rmax:
                            result.error(file, loc, f"value {val} above slot range max {rmax}")
            # gt/gte/lt/lte should not have missing value
            if val is None:
                result.error(file, loc, f"op '{op}' requires a value")

        elif op in ("is_unknown", "is_answered", "is_declined"):
            if val is not None:
                result.error(file, loc, f"op '{op}' should not have a value")

        elif op in ("eq", "ne"):
            if st == "bool" and not isinstance(val, bool):
                # bool comparison value should be boolean
                if not isinstance(val, (bool, int, float)):
                    result.error(file, loc, f"op '{op}' on bool slot '{sid}' expects boolean value")
            if st == "enum" and isinstance(val, str):
                if val not in slot.allowed_values:
                    result.error(file, loc, f"value '{val}' not in allowed_values of slot '{sid}': {slot.allowed_values}")

        elif op in ("in", "not_in"):
            if st == "bool":
                result.error(file, loc, f"op '{op}' not compatible with bool slot '{sid}'")
            if st == "enum":
                if isinstance(val, list):
                    for v in val:
                        if isinstance(v, str) and v not in slot.allowed_values:
                            result.error(file, loc, f"value '{v}' in list not in allowed_values of slot '{sid}'")
                else:
                    result.error(file, loc, f"op '{op}' expects a list value")

        elif op == "contains_any":
            if st != "enum" or not slot.multi:
                result.error(file, loc, f"op 'contains_any' only for multi enum slots; slot '{sid}' is {st}, multi={slot.multi}")
            if st == "enum" and isinstance(val, list):
                for v in val:
                    if isinstance(v, str) and v not in slot.allowed_values:
                        result.error(file, loc, f"value '{v}' in contains_any not in allowed_values of slot '{sid}'")


def check_redflag_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    slots: dict[str, SlotInfo],
) -> None:
    data = lf.data
    rules = data.get("rules", [])
    seen_ids: set[str] = set()
    for i, rule in enumerate(rules):
        rid = rule.get("rule_id")
        loc = f"rules[{i}].{rid or i}"

        if rid in seen_ids:
            result.error(lf.rel_path, loc, f"Duplicate rule_id: {rid}")
        seen_ids.add(rid)

        # scope
        scope = rule.get("scope", [])
        for s in scope:
            if s != "global" and s not in EXPECTED_MODULE_IDS:
                result.error(lf.rel_path, loc, f"scope contains unknown module: {s}")

        # condition
        cond = rule.get("condition")
        if cond:
            check_condition(result, lf.rel_path, f"{loc}.condition", cond, slots)

        # near_miss_condition
        nm = rule.get("near_miss_condition")
        if nm:
            check_condition(result, lf.rel_path, f"{loc}.near_miss_condition", nm, slots)

        # followup_slots
        fs = rule.get("followup_slots", [])
        for s in fs:
            if s not in slots:
                result.error(lf.rel_path, loc, f"followup_slot '{s}' not in slots.yaml")

        # on_unknown ask_followup -> followup_slots non-empty (schema already enforces, confirm)
        if rule.get("on_unknown") == "ask_followup" and not fs:
            result.error(lf.rel_path, loc, "on_unknown=ask_followup but followup_slots empty")

        # status check
        st = rule.get("status")
        if st in ("clinician_reviewed", "approved"):
            if not rule.get("sources"):
                result.error(lf.rel_path, loc, f"status={st} but sources empty")
            if rule.get("needs_clinician_review"):
                result.error(lf.rel_path, loc, f"status={st} but needs_clinician_review is true")


def check_question_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    slots: dict[str, SlotInfo],
) -> None:
    data = lf.data
    seen_ids: set[str] = set()
    questions = data.get("questions", [])

    for i, q in enumerate(questions):
        qid = q.get("question_id")
        loc = f"questions[{i}].{qid or i}"

        if qid in seen_ids:
            result.error(lf.rel_path, loc, f"Duplicate question_id: {qid}")
        seen_ids.add(qid)

        # slot exists
        slot_id = q.get("slot")
        if slot_id and slot_id not in slots:
            result.error(lf.rel_path, loc, f"slot '{slot_id}' not in slots.yaml")

        # also_fills
        af = q.get("also_fills", [])
        for s in af:
            if s not in slots:
                result.error(lf.rel_path, loc, f"also_fills '{s}' not in slots.yaml")

        # answer_options values
        slot_info = slots.get(slot_id) if slot_id else None
        ao = q.get("answer_options", [])
        if slot_info and slot_info.slot_type == "enum" and ao:
            for j, opt in enumerate(ao):
                v = opt.get("value")
                if v and v not in slot_info.allowed_values:
                    result.error(lf.rel_path, f"{loc}.answer_options[{j}]", f"value '{v}' not in allowed_values of slot '{slot_id}'")

        # precondition
        pc = q.get("precondition")
        if pc:
            check_condition(result, lf.rel_path, f"{loc}.precondition", pc, slots)

    # entry_condition
    ec = data.get("entry_condition")
    if ec:
        check_condition(result, lf.rel_path, "entry_condition", ec, slots)

    # stopping.stop_when
    stop = data.get("stopping", {})
    sw = stop.get("stop_when")
    if sw:
        check_condition(result, lf.rel_path, "stopping.stop_when", sw, slots)

    # required_slots: each must be filled by some question or be derived
    required = data.get("required_slots", [])
    filled: set[str] = set()
    for q in questions:
        if q.get("slot"):
            filled.add(q["slot"])
        for s in q.get("also_fills", []):
            filled.add(s)
    for rs in required:
        if rs not in slots:
            result.error(lf.rel_path, "required_slots", f"required_slot '{rs}' not in slots.yaml")
        elif rs not in filled and not slots[rs].derived:
            result.error(lf.rel_path, "required_slots", f"required_slot '{rs}' is not filled by any question and not derived")


def check_decision_table_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    slots: dict[str, SlotInfo],
) -> None:
    data = lf.data
    seen_ids: set[str] = set()
    rows = data.get("rows", [])

    module = data.get("module")
    if module and module not in EXPECTED_MODULE_IDS:
        result.error(lf.rel_path, "module", f"Unknown module: {module}")

    produced_levels: set[str] = set()
    priorities: list[int] = []

    for i, row in enumerate(rows):
        rid = row.get("row_id")
        loc = f"rows[{i}].{rid or i}"

        if rid in seen_ids:
            result.error(lf.rel_path, loc, f"Duplicate row_id: {rid}")
        seen_ids.add(rid)

        when = row.get("when")
        if when:
            check_condition(result, lf.rel_path, f"{loc}.when", when, slots)

        produced_levels.add(row.get("level"))

        p = row.get("priority")
        if p is not None:
            if p in priorities:
                result.error(lf.rel_path, loc, f"Duplicate priority: {p}")
            priorities.append(p)

        st = row.get("status")
        if st in ("clinician_reviewed", "approved"):
            if not row.get("sources"):
                result.error(lf.rel_path, loc, f"status={st} but sources empty")

    # default_row must exist (schema enforces, but confirm)
    if not data.get("default_row"):
        result.error(lf.rel_path, "default_row", "Missing default_row")

    # conflict_resolution first_match_by_priority -> every row needs priority
    cr = data.get("conflict_resolution")
    if cr == "first_match_by_priority":
        for i, row in enumerate(rows):
            if row.get("priority") is None:
                result.error(lf.rel_path, f"rows[{i}]", "conflict_resolution=first_match_by_priority but priority missing")

    # WARNING: levels never produced (skip for examples — they are format demos)
    if not lf.is_example:
        for level in EXPECTED_LEVEL_IDS:
            if level not in produced_levels and level != "EMERGENCY_NOW":
                result.warning(lf.rel_path, "rows", f"Level '{level}' is never produced by any row")


def check_selfcare_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    slots: dict[str, SlotInfo],
) -> None:
    data = lf.data
    seen_ids: set[str] = set()
    cards = data.get("cards", [])

    # Group by module: track which modules have SELF_CARE cards and escalation_criteria
    module_has_selfcare: dict[str, bool] = {}
    module_has_escalation: dict[str, bool] = {}

    for i, card in enumerate(cards):
        cid = card.get("card_id")
        loc = f"cards[{i}].{cid or i}"

        if cid in seen_ids:
            result.error(lf.rel_path, loc, f"Duplicate card_id: {cid}")
        seen_ids.add(cid)

        module = card.get("module")
        if module and module not in EXPECTED_MODULE_IDS:
            result.error(lf.rel_path, loc, f"Unknown module: {module}")

        levels = card.get("applicable_levels", [])
        has_self_care = "SELF_CARE" in levels
        is_escalation = card.get("card_type") == "escalation_criteria"

        if module:
            if has_self_care:
                module_has_selfcare[module] = True
            if has_self_care and is_escalation:
                module_has_escalation[module] = True

        # applies_when
        aw = card.get("applies_when")
        if aw:
            check_condition(result, lf.rel_path, f"{loc}.applies_when", aw, slots)

        # status checks
        st = card.get("status")
        if st in ("clinician_reviewed", "approved"):
            if not card.get("sources"):
                result.error(lf.rel_path, loc, f"status={st} but sources empty")
            if card.get("needs_clinician_review"):
                result.error(lf.rel_path, loc, f"status={st} but needs_clinician_review is true")

    # SELF_CARE + escalation_criteria combination check
    for module, has_sc in module_has_selfcare.items():
        if has_sc and not module_has_escalation.get(module):
            result.error(
                lf.rel_path, "cards",
                f"Module '{module}' has SELF_CARE cards but no escalation_criteria card for SELF_CARE"
            )


def check_facility_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    slots: dict[str, SlotInfo],
    global_ids: set[str] | None = None,
) -> None:
    data = lf.data
    seen_ids: set[str] = set()
    facilities = data.get("facilities", [])
    today = date.today()

    for i, fac in enumerate(facilities):
        fid = fac.get("facility_id")
        loc = f"facilities[{i}].{fid or i}"

        if fid in seen_ids:
            result.error(lf.rel_path, loc, f"Duplicate facility_id: {fid}")
        seen_ids.add(fid)
        if global_ids is not None:
            if fid in global_ids:
                result.error(lf.rel_path, loc, f"Duplicate facility_id across files: {fid}")
            global_ids.add(fid)

        # operating hours
        walk_in = fac.get("walk_in_available")
        op_hours = fac.get("operating_hours") or ""
        if walk_in is False and not op_hours:
            # walk_in_available is false and no operating_hours — but schema doesn't require it
            pass

        # urgent_og / a_e facilities should be walk-in (proxy for 24h)
        # facility schema has no explicit open_24h field; walk_in_available is the closest proxy
        fac_type = fac.get("type")
        if fac_type in ("urgent_og", "a_e") and not walk_in:
            result.warning(
                lf.rel_path, loc,
                f"type={fac_type} facility should have walk_in_available=true (proxy for 24h availability)"
            )

        # needs_verification (if present) -> WARNING
        # last_verified stale check
        lv = fac.get("last_verified")
        # facility-level last_verified isn't in the schema, but meta-level is
        meta = data.get("meta", {})
        meta_lv = meta.get("last_verified")
        check_lv = meta_lv
        if check_lv:
            try:
                lv_date = datetime.strptime(check_lv, "%Y-%m-%d").date()
                if (today - lv_date).days > 180:
                    result.warning(lf.rel_path, "meta.last_verified", f"last_verified is {(today - lv_date).days} days old (> 180)")
            except (ValueError, TypeError):
                pass

        # accepts_minors
        am = fac.get("accepts_minors")
        # The facility schema has accepts_minors as boolean, not "unknown"
        # If someone uses "unknown" string, it's a schema violation already

        # status checks
        st = fac.get("status")
        if st in ("clinician_reviewed", "approved"):
            if not fac.get("sources"):
                result.error(lf.rel_path, loc, f"status={st} but sources empty")


# ---------------------------------------------------------------------------
# Weight presets semantic checks
# ---------------------------------------------------------------------------

ALLOWED_RANKING_LEVELS = {"SEE_DOCTOR_24_48H", "BOOK_SOON"}
WEIGHT_SUM_TOLERANCE = 0.001


def check_weight_presets_semantics(
    result: ValidationResult,
    lf: LoadedFile,
) -> None:
    data = lf.data
    features = data.get("features", [])
    feature_ids: set[str] = set()
    for i, feat in enumerate(features):
        fid = feat.get("id")
        if fid and fid in feature_ids:
            result.error(lf.rel_path, f"features[{i}]", f"Duplicate feature id: {fid}")
        feature_ids.add(fid)

    ranking_levels = data.get("ranking_levels", [])
    ranking_levels_set = set(ranking_levels)

    # ranking_levels must not contain EMERGENCY_NOW or SELF_CARE
    for lv in ranking_levels:
        if lv in ("EMERGENCY_NOW", "SELF_CARE"):
            result.error(lf.rel_path, "ranking_levels", f"ranking_levels must not contain {lv}")

    # Check if ranking_levels contains only allowed levels
    for lv in ranking_levels:
        if lv not in ALLOWED_RANKING_LEVELS:
            result.error(lf.rel_path, "ranking_levels", f"ranking_levels contains unexpected level: {lv}")

    # default_weights_by_level checks
    dwbl = data.get("default_weights_by_level", {})
    _check_weights_block(result, lf, dwbl, "default_weights_by_level", ranking_levels_set, feature_ids)

    # bounds_by_level checks
    bbl = data.get("bounds_by_level", {})
    if not bbl:
        result.error(lf.rel_path, "bounds_by_level", "bounds_by_level is required and non-empty")
    else:
        # keys must match ranking_levels
        for key in bbl:
            if key not in ranking_levels_set:
                result.error(lf.rel_path, "bounds_by_level", f"bounds_by_level key '{key}' not in ranking_levels")
        # must cover all features
        for key, bounds in bbl.items():
            if isinstance(bounds, dict):
                covered = set(bounds.keys())
                missing = feature_ids - covered
                if missing:
                    result.error(
                        lf.rel_path, f"bounds_by_level.{key}",
                        f"bounds_by_level.{key} does not cover features: {missing}"
                    )
                for fid, bound in bounds.items():
                    if isinstance(bound, dict):
                        bmin = bound.get("min")
                        bmax = bound.get("max")
                        if bmin is not None and bmax is not None and bmin > bmax:
                            result.error(
                                lf.rel_path, f"bounds_by_level.{key}.{fid}",
                                f"bound min ({bmin}) > max ({bmax})"
                            )

    # presets checks
    presets = data.get("presets", [])
    seen_preset_ids: set[str] = set()
    for i, preset in enumerate(presets):
        pid = preset.get("preset_id")
        loc = f"presets[{i}].{pid or i}"
        if pid and pid in seen_preset_ids:
            result.error(lf.rel_path, loc, f"Duplicate preset_id: {pid}")
        seen_preset_ids.add(pid)

        wbl = preset.get("weights_by_level", {})
        _check_weights_block(result, lf, wbl, f"presets[{i}].weights_by_level", ranking_levels_set, feature_ids)

    # Also check that each weight falls within bounds
    for level, weights in dwbl.items():
        bounds_for_level = bbl.get(level, {})
        if isinstance(weights, dict) and isinstance(bounds_for_level, dict):
            for fid, w in weights.items():
                bound = bounds_for_level.get(fid)
                if isinstance(bound, dict):
                    bmin = bound.get("min")
                    bmax = bound.get("max")
                    if bmin is not None and isinstance(w, (int, float)) and w < bmin:
                        result.error(
                            lf.rel_path, f"default_weights_by_level.{level}.{fid}",
                            f"weight {w} below bound min {bmin}"
                        )
                    if bmax is not None and isinstance(w, (int, float)) and w > bmax:
                        result.error(
                            lf.rel_path, f"default_weights_by_level.{level}.{fid}",
                            f"weight {w} above bound max {bmax}"
                        )

    for i, preset in enumerate(presets):
        wbl = preset.get("weights_by_level", {})
        for level, weights in wbl.items():
            bounds_for_level = bbl.get(level, {})
            if isinstance(weights, dict) and isinstance(bounds_for_level, dict):
                for fid, w in weights.items():
                    bound = bounds_for_level.get(fid)
                    if isinstance(bound, dict):
                        bmin = bound.get("min")
                        bmax = bound.get("max")
                        if bmin is not None and isinstance(w, (int, float)) and w < bmin:
                            result.error(
                                lf.rel_path, f"presets[{i}].weights_by_level.{level}.{fid}",
                                f"weight {w} below bound min {bmin}"
                            )
                        if bmax is not None and isinstance(w, (int, float)) and w > bmax:
                            result.error(
                                lf.rel_path, f"presets[{i}].weights_by_level.{level}.{fid}",
                                f"weight {w} above bound max {bmax}"
                            )


def _check_weights_block(
    result: ValidationResult,
    lf: LoadedFile,
    weights_block: dict,
    block_name: str,
    ranking_levels_set: set[str],
    feature_ids: set[str],
) -> None:
    """Check a weights_by_level block for level keys, feature ids, and sum=1."""
    if not weights_block:
        result.error(lf.rel_path, block_name, f"{block_name} is empty or missing")
        return
    for level, weights in weights_block.items():
        if level not in ranking_levels_set:
            result.error(lf.rel_path, f"{block_name}.{level}", f"level '{level}' not in ranking_levels")
        if isinstance(weights, dict):
            for fid in weights:
                if fid not in feature_ids:
                    result.error(lf.rel_path, f"{block_name}.{level}.{fid}", f"feature id '{fid}' not defined in features")
            total = sum(weights.values())
            if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
                result.error(
                    lf.rel_path, f"{block_name}.{level}",
                    f"weight sum is {total}, expected 1.0 (±{WEIGHT_SUM_TOLERANCE})"
                )


# ---------------------------------------------------------------------------
# Questionnaire mapping semantic checks
# ---------------------------------------------------------------------------

# Valid values for set_profile_field effects (cross-check with user_profile schema)
PROFILE_FIELD_VALUES = {
    "travel_mode": {"walking", "public_transport", "driving", "ride_hailing", "unknown"},
    "residency_status": {"citizen", "pr", "other", "unknown"},
    "has_chas": {"yes", "no", "unknown"},
    "insurance_add": {"private", "student", "employer", "other", "none", "unknown"},
}


def check_questionnaire_semantics(
    result: ValidationResult,
    lf: LoadedFile,
    weight_presets: dict | None,
) -> None:
    """Check questionnaire mapping semantic constraints against weight_presets."""
    data = lf.data
    questions = data.get("questions", [])

    # Extract feature ids and preset ids from weight_presets
    wp_features: set[str] = set()
    wp_presets: set[str] = set()
    wp_ranking_levels: set[str] = set()
    wp_meta_id = None
    wp_meta_version = None
    if weight_presets:
        for feat in weight_presets.get("features", []):
            wp_features.add(feat.get("id"))
        for preset in weight_presets.get("presets", []):
            wp_presets.add(preset.get("preset_id"))
        wp_ranking_levels = set(weight_presets.get("ranking_levels", []))
        wp_meta = weight_presets.get("meta", {})
        wp_meta_id = wp_meta.get("id")
        wp_meta_version = wp_meta.get("version")

    seen_question_ids: set[str] = set()
    for i, q in enumerate(questions):
        qid = q.get("question_id")
        loc = f"questions[{i}].{qid or i}"

        if qid and qid in seen_question_ids:
            result.error(lf.rel_path, loc, f"Duplicate question_id: {qid}")
        seen_question_ids.add(qid)

        seen_option_ids: set[str] = set()
        options = q.get("options", [])
        multi_select = q.get("multi_select", False)

        # Track multiply effects per feature for conflict detection
        multiply_by_feature: dict[str, list[tuple[str, float]]] = {}

        for j, opt in enumerate(options):
            oid = opt.get("option_id")
            oloc = f"{loc}.options[{j}].{oid or j}"
            if oid and oid in seen_option_ids:
                result.error(lf.rel_path, oloc, f"Duplicate option_id: {oid}")
            seen_option_ids.add(oid)

            effects = opt.get("effects", [])
            for k, eff in enumerate(effects):
                eloc = f"{oloc}.effects[{k}]"
                etype = eff.get("type")

                if etype == "set_base_preset":
                    pid = eff.get("preset_id")
                    if wp_presets and pid not in wp_presets:
                        result.error(lf.rel_path, eloc, f"set_base_preset references non-existent preset_id: {pid}")

                elif etype in ("add_delta", "multiply"):
                    fid = eff.get("feature")
                    if wp_features and fid not in wp_features:
                        result.error(lf.rel_path, eloc, f"effect references non-existent feature: {fid}")
                    levels = eff.get("levels", [])
                    for lv in levels:
                        if wp_ranking_levels and lv not in wp_ranking_levels:
                            result.error(lf.rel_path, eloc, f"levels contains '{lv}' not in weight_presets ranking_levels")

                    if etype == "multiply":
                        factor = eff.get("factor")
                        if fid:
                            multiply_by_feature.setdefault(fid, []).append((oid or "", factor or 0))

                elif etype == "set_profile_field":
                    field = eff.get("field")
                    value = eff.get("value")
                    if field and field in PROFILE_FIELD_VALUES:
                        valid_values = PROFILE_FIELD_VALUES[field]
                        if value not in valid_values:
                            result.error(
                                lf.rel_path, eloc,
                                f"set_profile_field '{field}' value '{value}' not in {valid_values}"
                            )

        # multi_select=false: check for multiply conflicts (same feature, same factor → WARNING)
        if not multi_select and multiply_by_feature:
            for fid, entries in multiply_by_feature.items():
                if len(entries) >= 2:
                    factors = [f for _, f in entries]
                    if len(set(factors)) == 1:
                        result.warning(
                            lf.rel_path, loc,
                            f"multi_select=false but multiple options use multiply on feature '{fid}' with same factor {factors[0]}"
                        )

    # Check weight_presets version consistency
    q_meta = data.get("meta", {})
    q_version = q_meta.get("version")
    if wp_meta_version and q_version and q_version != wp_meta_version:
        result.warning(
            lf.rel_path, "meta.version",
            f"questionnaire meta.version ({q_version}) differs from weight_presets meta.version ({wp_meta_version})"
        )


# ---------------------------------------------------------------------------
# Batch 3b: MVP source-check (non-empty sources for content dirs)
# ---------------------------------------------------------------------------


def check_mvp_sources(result: ValidationResult, files: list[LoadedFile]) -> None:
    """MVP rule: every redflag rule, decision table row, and selfcare card must have non-empty sources."""
    for lf in files:
        if lf.is_example:
            continue  # Examples and test fixtures are exempt
        data = lf.data
        if not isinstance(data, dict):
            continue
        # Determine which dir this came from
        dir_name = lf.rel_path.split("/")[0] if "/" in lf.rel_path else ""
        if dir_name not in SOURCE_CHECK_DIRS:
            continue

        if dir_name == "rules":
            for i, rule in enumerate(data.get("rules", [])):
                if not rule.get("sources"):
                    result.error(lf.rel_path, f"rules[{i}]", "sources must not be empty (MVP requirement)")
        elif dir_name == "decision_tables":
            for i, row in enumerate(data.get("rows", [])):
                if not row.get("sources"):
                    result.error(lf.rel_path, f"rows[{i}]", "sources must not be empty (MVP requirement)")
        elif dir_name == "selfcare":
            for i, card in enumerate(data.get("cards", [])):
                if not card.get("sources"):
                    result.error(lf.rel_path, f"cards[{i}]", "sources must not be empty (MVP requirement)")


# ---------------------------------------------------------------------------
# Batch 4: Content safety lint
# ---------------------------------------------------------------------------


def load_lint_denylist(project_root: Path) -> dict[str, list[str]] | None:
    lint_path = project_root / LINT_FILE
    if not lint_path.exists():
        return None
    return _yaml_load(lint_path)


def _extract_i18n_texts(obj: Any, loc: str = "") -> list[tuple[str, dict[str, str]]]:
    """Recursively find all i18n_text objects and return (location, {lang: text})."""
    results: list[tuple[str, dict[str, str]]] = []
    if isinstance(obj, dict):
        # Check if this is an i18n_text object (has 'en' key with string value)
        if "en" in obj and isinstance(obj["en"], str) and all(
            k in ("en", "zh", "ms", "ta") for k in obj.keys()
        ):
            texts: dict[str, str] = {}
            for lang in ("en", "zh", "ms", "ta"):
                if lang in obj and isinstance(obj[lang], str):
                    texts[lang] = obj[lang]
            results.append((loc, texts))
            return results  # Don't recurse into i18n_text values (they're strings)
        for k, v in obj.items():
            results.extend(_extract_i18n_texts(v, f"{loc}.{k}" if loc else k))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_extract_i18n_texts(item, f"{loc}[{i}]"))
    return results


def run_lint(
    result: ValidationResult,
    files: list[LoadedFile],
    denylist: dict | None,
) -> None:
    if not denylist:
        result.warning("lint_denylist.yaml", "", "Lint denylist not found, skipping content safety scan")
        return

    dosage_patterns = denylist.get("dosage_patterns", [])
    drug_names = denylist.get("drug_names", [])
    diagnostic_phrases = denylist.get("diagnostic_phrases", [])

    has_ms_or_ta = False

    for lf in files:
        data = lf.data
        if not isinstance(data, dict):
            continue

        # Determine which text fields to scan based on file type
        dir_name = lf.rel_path.split("/")[0] if "/" in lf.rel_path else ""
        if dir_name not in ("selfcare", "rules", "questions", "decision_tables"):
            continue
        if lf.is_example:
            continue  # Don't lint example files

        i18n_texts = _extract_i18n_texts(data)
        for loc, texts in i18n_texts:
            # Skip rationale fields for decision tables (they're for reviewers, not users)
            # The task says: "决策表的 rationale（给审核者看的内部说明不扫）"
            # But user_note for redflag IS scanned
            if dir_name == "decision_tables" and ".rationale" in loc:
                continue

            for lang, text in texts.items():
                if lang in ("ms", "ta"):
                    has_ms_or_ta = True
                    continue  # ms/ta not scanned

                text_lower = text.lower()

                # Dosage patterns (ERROR)
                for pattern in dosage_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        result.error(lf.rel_path, f"{loc}.{lang}", f"Lint (dosage) match: pattern '{pattern}' in text")

                # Drug names (ERROR)
                for drug in drug_names:
                    if drug.lower() in text_lower:
                        result.error(lf.rel_path, f"{loc}.{lang}", f"Lint (drug name) match: '{drug}' in text")

                # Diagnostic phrases (WARNING)
                for phrase in diagnostic_phrases:
                    if phrase.lower() in text_lower:
                        result.warning(lf.rel_path, f"{loc}.{lang}", f"Lint (diagnostic phrase) match: '{phrase}' in text")

        # Selfcare: attestation vs lint mismatch
        if dir_name == "selfcare":
            cards = data.get("cards", [])
            for i, card in enumerate(cards):
                attestation = card.get("content_attestation", {})
                mentions_drug = attestation.get("mentions_specific_drug", False)
                gives_dosage = attestation.get("gives_dosage", False)

                card_texts = _extract_i18n_texts(card)
                for loc2, texts2 in card_texts:
                    for lang2, text2 in texts2.items():
                        if lang2 in ("ms", "ta"):
                            continue
                        text2_lower = text2.lower()
                        # Check if lint finds drug/dosage despite attestation saying false
                        lint_drug_hit = any(d.lower() in text2_lower for d in drug_names)
                        lint_dosage_hit = any(re.search(p, text2, re.IGNORECASE) for p in dosage_patterns)
                        if (lint_drug_hit and not mentions_drug) or (lint_dosage_hit and not gives_dosage):
                            result.error(
                                lf.rel_path,
                                f"cards[{i}]{loc2}.{lang2}",
                                "content_attestation says no drug/dosage but lint found a match (attestation mismatch)"
                            )

    if has_ms_or_ta:
        result.info("", "", "ms/ta 文本需人工审核 (ms/ta text requires manual review)")


# ---------------------------------------------------------------------------
# Batch 3: Example validation helpers
# ---------------------------------------------------------------------------


def check_examples(
    result: ValidationResult,
    example_files: list[LoadedFile],
    schemas: dict[str, dict],
    registry: Registry,
    slots: dict[str, SlotInfo],
) -> None:
    """Check that valid examples pass and invalid examples fail schema validation."""
    fc = FormatChecker()
    for lf in example_files:
        if lf.schema_name is None or lf.schema_name not in schemas:
            continue
        schema = schemas[lf.schema_name]
        validator = Draft202012Validator(schema, registry=registry, format_checker=fc)
        errors = list(validator.iter_errors(lf.data))

        # Must check "invalid" first since "invalid" contains "valid" as substring
        is_invalid = ".invalid" in lf.rel_path or "/invalid" in lf.rel_path
        is_valid = not is_invalid and ".valid" in lf.rel_path

        if is_valid and errors:
            for e in errors:
                loc = e.json_path if e.json_path else "$"
                result.error(lf.rel_path, loc, f"Valid example failed schema: {e.message}")
        elif is_invalid and not errors:
            result.error(lf.rel_path, "", "Invalid example passed schema (expected to fail)")

    # Also run semantic checks on valid examples (they should pass)
    for lf in example_files:
        if ".invalid" in lf.rel_path or "/invalid" in lf.rel_path:
            continue  # Don't run semantic checks on invalid examples
        if ".valid" not in lf.rel_path:
            continue
        dir_name = lf.schema_name
        if dir_name == "redflag_rules":
            check_redflag_semantics(result, lf, slots)
        elif dir_name == "question_tree":
            check_question_semantics(result, lf, slots)
        elif dir_name == "decision_table":
            check_decision_table_semantics(result, lf, slots)
        elif dir_name == "selfcare_card":
            check_selfcare_semantics(result, lf, slots)
        elif dir_name == "facility":
            check_facility_semantics(result, lf, slots)
        elif dir_name == "weight_presets":
            check_weight_presets_semantics(result, lf)
        elif dir_name == "questionnaire_mapping":
            # For examples, weight_presets_data is not available; pass None
            check_questionnaire_semantics(result, lf, None)


# ---------------------------------------------------------------------------
# Main validation pipeline
# ---------------------------------------------------------------------------


def validate(contracts_dir: Path, project_root: Path) -> ValidationResult:
    result = ValidationResult()

    # Load schemas and build registry
    schemas = _load_schemas(contracts_dir)
    registry = _build_registry(schemas)

    # Batch 1: Load and schema-validate content files
    content_files = _load_content_files(contracts_dir)
    example_files = _load_example_files(contracts_dir)
    all_files = content_files + example_files

    validate_schema(result, all_files, schemas, registry)

    # Batch 2: Dictionary checks
    check_levels(result, contracts_dir)
    check_modules(result, contracts_dir)
    slots = check_slots(result, contracts_dir)

    # Batch 3: Semantic cross-checks on content files
    global_facility_ids: set[str] = set()

    # Check meta blocks on all content files (reviewed/approved requires reviewer+last_verified)
    for lf in content_files:
        if isinstance(lf.data, dict):
            _check_meta(result, lf.rel_path, lf.data.get("meta"))

    for lf in content_files:
        if lf.schema_name == "redflag_rules":
            check_redflag_semantics(result, lf, slots)
        elif lf.schema_name == "question_tree":
            check_question_semantics(result, lf, slots)
        elif lf.schema_name == "decision_table":
            check_decision_table_semantics(result, lf, slots)
        elif lf.schema_name == "selfcare_card":
            check_selfcare_semantics(result, lf, slots)
        elif lf.schema_name == "facility":
            check_facility_semantics(result, lf, slots, global_facility_ids)
        elif lf.schema_name == "weight_presets":
            check_weight_presets_semantics(result, lf)

    # Load weight_presets data for cross-file questionnaire checks
    weight_presets_data: dict | None = None
    for lf in content_files:
        if lf.schema_name == "weight_presets" and isinstance(lf.data, dict):
            weight_presets_data = lf.data
            break

    for lf in content_files:
        if lf.schema_name == "questionnaire_mapping":
            check_questionnaire_semantics(result, lf, weight_presets_data)

    # Batch 3b: MVP source checks
    check_mvp_sources(result, content_files)

    # Batch 3: Example validation
    check_examples(result, example_files, schemas, registry, slots)

    # Batch 4: Content safety lint
    denylist = load_lint_denylist(project_root)
    run_lint(result, content_files, denylist)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Grandma contract validator")
    parser.add_argument(
        "--contracts-dir",
        default="contracts",
        help="Path to the contracts directory (default: contracts)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARNINGs as failures too",
    )
    args = parser.parse_args()

    # Resolve paths relative to project root (parent of tools/)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    contracts_dir = project_root / args.contracts_dir

    if not contracts_dir.is_dir():
        print(f"Error: contracts directory not found: {contracts_dir}")
        return 1

    result = validate(contracts_dir, project_root)

    # Print grouped output
    output = result.grouped_output()
    if output:
        print(output)

    # Print summary
    print(result.summary())

    if result.has_errors:
        return 1
    if args.strict and result.has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
