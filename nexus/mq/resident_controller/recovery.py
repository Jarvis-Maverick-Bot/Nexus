"""Restart recovery classification for resident controller checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResidentControllerCheckpoint:
    run_id: str
    service_state: str
    pending_assignments: dict[str, dict[str, Any]]
    completed_assignments: dict[str, dict[str, Any]]
    replay_allowed: bool = False
    not_business_completion: bool = True


@dataclass
class RecoveryClassificationResult:
    classifications: dict[str, str]
    replay_allowed: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def classify_restart_recovery(checkpoint: ResidentControllerCheckpoint) -> RecoveryClassificationResult:
    classifications: dict[str, str] = {}
    errors: list[str] = []
    for assignment_id in sorted(checkpoint.completed_assignments):
        classifications[assignment_id] = "observed_complete"
    for assignment_id, payload in sorted(checkpoint.pending_assignments.items()):
        if assignment_id in classifications:
            continue
        if payload.get("quarantined"):
            classifications[assignment_id] = "quarantined"
        elif checkpoint.replay_allowed and payload.get("idempotency_key") and checkpoint.run_id:
            classifications[assignment_id] = "replay_eligible"
        else:
            classifications[assignment_id] = "pending_reconciliation"
            errors.append("REPLAY_BLOCKED_PENDING_RECONCILIATION")
    return RecoveryClassificationResult(
        classifications=classifications,
        replay_allowed=checkpoint.replay_allowed and not errors,
        errors=_dedupe(errors),
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
