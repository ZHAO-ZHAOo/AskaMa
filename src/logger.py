"""Event logger for AI Grandma.

Writes anonymized event logs in JSON Lines format.
Never stores raw user text, exact coordinates, FinalResponse.text, or questionnaire answers.
"""

from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
import uuid


# Fields that must be redacted from any event payload
SENSITIVE_FIELDS = {
    "raw_text", "original_text", "user_text", "message",
    "exact_lat", "exact_lng", "coordinates", "phone", "name",
    "address", "postal_code", "text",
}


def _redact(data: dict) -> dict:
    """Remove sensitive fields from a dict."""
    cleaned = {}
    for k, v in data.items():
        if k in SENSITIVE_FIELDS:
            cleaned[k] = "[redacted]"
        elif isinstance(v, dict):
            cleaned[k] = _redact(v)
        elif isinstance(v, list):
            cleaned[k] = [_redact(item) if isinstance(item, dict) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned


def _anon_session_id(session_id: str) -> str:
    """Hash session ID for anonymization."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:16]


def _anon_outcome_key(session_id: str) -> str:
    """Generate anonymous outcome_link_key for future follow-up."""
    return hashlib.sha256(f"{session_id}-outcome".encode()).hexdigest()[:16]


@dataclass
class EventLogger:
    """Logger that writes events to a JSONL file."""
    log_path: Path
    versions: dict = field(default_factory=dict)

    def __post_init__(self):
        self.log_path = Path(self.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        session_id: str,
        turn_id: int,
        event_type: str,
        payload: dict,
    ) -> None:
        """Write one event to the log."""
        anon_sid = _anon_session_id(session_id)
        event = {
            "session_id": anon_sid,
            "turn_id": turn_id,
            "timestamp": int(time.time()),
            "event_type": event_type,
            "versions": self.versions,
            "outcome_link_key": _anon_outcome_key(session_id),
            "payload": _redact(payload),
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_batch(self, events: list[dict]) -> None:
        """Write multiple events."""
        for ev in events:
            self.log(
                ev.get("session_id", "unknown"),
                ev.get("turn_id", 0),
                ev.get("event_type", "unknown"),
                ev.get("payload", {}),
            )


def create_logger(log_dir: Path | str = "data/logs") -> EventLogger:
    """Create an EventLogger with a timestamped log file."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"events_{timestamp}.jsonl"
    return EventLogger(log_path=log_path)
