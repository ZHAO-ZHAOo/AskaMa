"""AI Grandma configuration loader.

Loads and validates all contract files at startup, producing a ConfigBundle.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfigBundle:
    """All loaded configuration data."""
    levels: dict
    modules: list
    slots: list
    redflag_rules: list = field(default_factory=list)
    question_trees: dict = field(default_factory=dict)
    core_questions: dict = field(default_factory=dict)
    decision_tables: dict = field(default_factory=dict)
    selfcare_cards: dict = field(default_factory=dict)
    facilities: list = field(default_factory=list)
    weight_presets: dict = field(default_factory=dict)
    questionnaire: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)

    @property
    def module_ids(self) -> list[str]:
        return [m["id"] for m in self.modules]

    def get_slot(self, slot_id: str) -> dict | None:
        for s in self.slots:
            if s["id"] == slot_id:
                return s
        return None

    def get_slot_value_label(self, slot_id: str, value: Any, lang: str = "en") -> str:
        slot = self.get_slot(slot_id)
        if not slot:
            return str(value)
        if slot.get("allowed_values"):
            for av in slot["allowed_values"]:
                if av["id"] == value:
                    return av.get("label", {}).get(lang, str(value))
        return str(value)


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(contracts_dir: Path | str) -> ConfigBundle:
    """Load all contract files from the contracts directory."""
    contracts_dir = Path(contracts_dir)

    levels_data = _load_yaml(contracts_dir / "levels.yaml")
    modules_data = _load_yaml(contracts_dir / "modules.yaml")
    slots_data = _load_yaml(contracts_dir / "slots.yaml")

    bundle = ConfigBundle(
        levels=levels_data,
        modules=modules_data.get("modules", []),
        slots=slots_data.get("slots", []),
    )

    # Load redflag rules
    rules_dir = contracts_dir / "rules"
    if rules_dir.exists():
        for yml in sorted(rules_dir.glob("*.yaml")):
            data = _load_yaml(yml)
            if data and "rules" in data:
                bundle.redflag_rules.extend(data["rules"])

    # Load question trees
    q_dir = contracts_dir / "questions"
    if q_dir.exists():
        for yml in sorted(q_dir.glob("*.yaml")):
            data = _load_yaml(yml)
            if data and "module" in data:
                if data["module"] == "core":
                    # Cross-module screening question set (not a triage module)
                    bundle.core_questions = data
                else:
                    bundle.question_trees[data["module"]] = data

    # Load decision tables
    dt_dir = contracts_dir / "decision_tables"
    if dt_dir.exists():
        for yml in sorted(dt_dir.glob("*.yaml")):
            data = _load_yaml(yml)
            if data and "module" in data:
                bundle.decision_tables[data["module"]] = data

    # Load selfcare cards
    sc_dir = contracts_dir / "selfcare"
    if sc_dir.exists():
        for yml in sorted(sc_dir.glob("*.yaml")):
            data = _load_yaml(yml)
            if data and "cards" in data:
                # Selfcare files may have module at top level or per-card
                if "module" in data:
                    bundle.selfcare_cards[data["module"]] = data
                elif data.get("cards"):
                    # Use the first card's module as key
                    mod = data["cards"][0].get("module", "unknown")
                    bundle.selfcare_cards[mod] = data

    # Load facilities
    fac_dir = contracts_dir / "facilities"
    if fac_dir.exists():
        for yml in sorted(fac_dir.glob("*.yaml")):
            data = _load_yaml(yml)
            if data and "facilities" in data:
                bundle.facilities.extend(data["facilities"])

    # Load weight presets
    wp_path = contracts_dir / "weights" / "weight_presets.yaml"
    if wp_path.exists():
        bundle.weight_presets = _load_yaml(wp_path)

    # Load questionnaire
    qm_path = contracts_dir / "questionnaire" / "questionnaire_mapping.yaml"
    if qm_path.exists():
        bundle.questionnaire = _load_yaml(qm_path)

    # Build versions dict
    versions: dict[str, str] = {}
    for source in [levels_data, modules_data, slots_data]:
        meta = source.get("meta", {})
        if meta.get("id"):
            versions[meta["id"]] = meta.get("version", "unknown")
    for rule_file in sorted((contracts_dir / "rules").glob("*.yaml")) if (contracts_dir / "rules").exists() else []:
        meta = _load_yaml(rule_file).get("meta", {})
        if meta.get("id"):
            versions[meta["id"]] = meta.get("version", "unknown")
    versions["contracts_bundle"] = "0.3.0"
    bundle.versions = versions

    return bundle
