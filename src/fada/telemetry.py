"""Append-only, side-effect-free decision evidence for offline FADA replays."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DECISION_LEDGER_SCHEMA_VERSION = "fada-decision-ledger/v1"


@dataclass(frozen=True, slots=True)
class DecisionLedgerEntry:
    decision_id: str
    trace_id: str
    sequence: int
    policy_version: str
    baseline_policy_version: str
    action: str
    task_id: str | None
    worker_id: str | None
    baseline_task_id: str | None
    baseline_worker_id: str | None
    reason: str
    projected_makespan: float | None
    baseline_projected_makespan: float | None
    confidence: float
    observed_elapsed_seconds: float | None
    estimator_version: str = "scenario-estimator/0.1"
    controller_version: str | None = None
    capacity_recommendation_id: str | None = None
    read_only: bool = True
    schema_version: str = DECISION_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DECISION_LEDGER_SCHEMA_VERSION:
            raise ValueError("unsupported decision ledger schema")
        if not self.decision_id or not self.trace_id or self.sequence < 0:
            raise ValueError("decision identity is invalid")
        if not self.policy_version or not self.baseline_policy_version:
            raise ValueError("policy versions are required")
        if not self.estimator_version:
            raise ValueError("estimator version is required")
        if self.controller_version is not None and not self.controller_version:
            raise ValueError("controller version cannot be empty")
        if self.capacity_recommendation_id is not None and not self.capacity_recommendation_id:
            raise ValueError("capacity recommendation identity cannot be empty")
        if self.action not in {"dispatch", "fallback", "wait"}:
            raise ValueError("unsupported decision action")
        if not isinstance(self.read_only, bool) or not self.read_only:
            raise ValueError("decision ledger is observational only")


def append_entry(path: Path, entry: DecisionLedgerEntry) -> str:
    """Append one complete JSON object and fsync it before returning its digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(asdict(entry), sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError("partial ledger write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return hashlib.sha256(encoded).hexdigest()


def read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("ledger has an incomplete final record")
    entries = [json.loads(line) for line in raw.splitlines() if line]
    identities = [str(item.get("decision_id", "")) for item in entries]
    if len(identities) != len(set(identities)) or not all(identities):
        raise ValueError("ledger decision identities must be unique")
    for item in entries:
        DecisionLedgerEntry(**item)
    return entries
