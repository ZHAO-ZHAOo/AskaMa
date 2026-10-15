"""L4 Facility recommendation engine.

Hard-filters facilities based on level and module requirements,
then ranks by weighted score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


FEE_TIER_SCORE = {
    "free": 1.0,
    "low": 0.8,
    "moderate": 0.5,
    "high": 0.2,
}


@dataclass
class RankedFacility:
    facility: dict
    score: float
    feature_scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "facility_id": self.facility.get("facility_id", ""),
            "name": self.facility.get("name", ""),
            "type": self.facility.get("type", ""),
            "address": self.facility.get("address", ""),
            "phone": self.facility.get("phone", ""),
            "operating_hours": self.facility.get("operating_hours", ""),
            "website": self.facility.get("website", ""),
            "fee_tier": self.facility.get("fee_tier", ""),
            "walk_in_available": self.facility.get("walk_in_available", False),
            "lat": self.facility.get("lat"),
            "lng": self.facility.get("lng"),
            "languages": self.facility.get("languages", []),
            "score": self.score,
            "feature_scores": self.feature_scores,
        }


@dataclass
class RankedPlaces:
    ranked: list = field(default_factory=list)
    excluded: list = field(default_factory=list)
    weights_used: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ranked": [r.to_dict() if isinstance(r, RankedFacility) else r for r in self.ranked],
            "excluded": self.excluded,
            "weights_used": self.weights_used,
        }


def _hard_filter(
    facilities: list[dict],
    level: str,
    module: str,
) -> tuple[list[dict], list[dict]]:
    """Hard-filter facilities based on level."""
    eligible = []
    excluded = []

    for fac in facilities:
        fac_type = fac.get("type", "")
        is_emergency = level == "EMERGENCY_NOW"

        if is_emergency:
            # Emergency: only urgent_og and a_e
            if fac_type in ("urgent_og", "a_e"):
                eligible.append(fac)
            else:
                excluded.append({"facility_id": fac.get("facility_id", ""), "reason": "not_emergency_capable"})
        elif level == "SEE_DOCTOR_24_48H":
            # 24-48h: urgent_og, a_e, polyclinic, chas_gp, private_gp
            if fac_type in ("urgent_og", "a_e", "polyclinic", "chas_gp", "private_gp"):
                eligible.append(fac)
            else:
                excluded.append({"facility_id": fac.get("facility_id", ""), "reason": "type_not_suitable_for_24_48h"})
        elif level == "BOOK_SOON":
            # Book soon: all types except a_e (for non-emergencies)
            if fac_type in ("polyclinic", "chas_gp", "private_gp", "private_gynae", "soc", "urgent_og"):
                eligible.append(fac)
            else:
                excluded.append({"facility_id": fac.get("facility_id", ""), "reason": "type_not_suitable_for_booking"})
        else:
            eligible.append(fac)

    return eligible, excluded


def _score_facility(
    fac: dict,
    weights: dict,
    ui_language: str = "en",
    user_area: str | None = None,
) -> tuple[float, dict]:
    """Compute weighted score for a facility."""
    feature_scores = {}

    # travel_time: approximate by type (demo without OneMap)
    # urgent_og/a_e are usually at hospitals, slightly farther
    fac_type = fac.get("type", "")
    if fac_type in ("urgent_og", "a_e"):
        feature_scores["travel_time"] = 0.5
    else:
        feature_scores["travel_time"] = 0.8

    # cost
    fee_tier = fac.get("fee_tier", "moderate")
    feature_scores["cost"] = FEE_TIER_SCORE.get(fee_tier, 0.5)

    # accessibility
    walk_in = fac.get("walk_in_available", False)
    accepts_minors = fac.get("accepts_minors", False)
    feature_scores["accessibility"] = (
        0.4 * (1.0 if walk_in else 0.0) +
        0.3 * (1.0 if accepts_minors else 0.0) +
        0.3 * 0.5  # baseline
    )

    # condition_fit
    has_gynae = fac.get("has_gynaecology", False)
    if fac_type in ("urgent_og", "a_e"):
        feature_scores["condition_fit"] = 0.9
    elif has_gynae:
        feature_scores["condition_fit"] = 0.8
    elif fac_type in ("polyclinic", "chas_gp", "private_gp"):
        feature_scores["condition_fit"] = 0.6
    else:
        feature_scores["condition_fit"] = 0.4

    # language_match
    langs = fac.get("languages", ["en"])
    feature_scores["language_match"] = 1.0 if ui_language in langs else 0.3

    # Weighted score
    total = 0.0
    for feat, w in weights.items():
        total += feature_scores.get(feat, 0.0) * w

    return total, feature_scores


def recommend_facilities(
    facilities: list[dict],
    level: str,
    module: str,
    weights_by_level: dict,
    ui_language: str = "en",
    user_area: str | None = None,
) -> RankedPlaces:
    """Filter and rank facilities for the given level."""
    # Get weights for this level
    weights = weights_by_level.get(level, weights_by_level.get("SEE_DOCTOR_24_48H", {}))

    # Hard filter
    eligible, excluded = _hard_filter(facilities, level, module)

    # Score and sort
    ranked_list = []
    for fac in eligible:
        score, feature_scores = _score_facility(fac, weights, ui_language, user_area)
        ranked_list.append(RankedFacility(facility=fac, score=score, feature_scores=feature_scores))

    ranked_list.sort(key=lambda r: r.score, reverse=True)

    result = RankedPlaces(weights_used=weights)
    result.ranked = ranked_list
    result.excluded = excluded

    return result
