"""Candidate Adapter run-state reconciliation contracts.

These helpers compare platform run-state snapshots with local adapter facts.
They do not start runtimes, publish broker messages, or claim business success.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from nexus.mq.candidate_adapter_session_store import CandidateAdapterSession


RECONCILIATION_SCHEMA_VERSION = "4.19.run_state_reconciliation.v1"
BLOCKED_STATE_DIVERGENCE = "BLOCKED_STATE_DIVERGENCE"


@dataclass
class RunStateMismatch:
    field: str
    platform_value: str
    local_value: str
    evidence_ref: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class RunStateReconciliation:
    reconciliation_id: str
    schema_version: str
    generated_at: str
    run_id: str
    local_state_hash: str
    platform_snapshot_id: str
    platform_snapshot_hash: str
    status: str
    mismatches: list[RunStateMismatch] = field(default_factory=list)
    required_action: str = "continue"
    error_code: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    reconciliation_record_ref: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mismatches"] = [item.to_dict() for item in self.mismatches]
        return data


def reconcile_run_state(
    *,
    session: CandidateAdapterSession,
    platform_snapshot: dict[str, Any],
    package_manifest: dict[str, Any],
    generated_at: str,
) -> RunStateReconciliation:
    mismatches: list[RunStateMismatch] = []
    evidence_ref = str(package_manifest.get("manifest_ref") or platform_snapshot.get("package_manifest_ref") or "")
    _compare(mismatches, "agent_id", platform_snapshot.get("target_agent_id"), session.agent_id, evidence_ref)
    _compare(mismatches, "runtime_instance_id", platform_snapshot.get("runtime_instance_id"), session.runtime_instance_id, evidence_ref)
    _compare(mismatches, "assignment_id", platform_snapshot.get("assignment_id"), _active_value(session.active_assignment_refs), evidence_ref)
    clean_tuple = _dict(platform_snapshot.get("clean_run_tuple"))
    _compare(mismatches, "idempotency_key", clean_tuple.get("idempotency_key"), _active_value(session.active_idempotency_keys), evidence_ref)
    _compare(mismatches, "lifecycle_decision_id", clean_tuple.get("lifecycle_decision_id"), _active_value(session.active_decision_ids), evidence_ref)
    _compare(mismatches, "reservation_lease_id", clean_tuple.get("reservation_lease_id"), _active_value(session.active_reservation_lease_ids), evidence_ref)
    _compare_if_present(mismatches, "duplicate_replay_status", platform_snapshot.get("duplicate_replay_status"), package_manifest.get("duplicate_replay_status"), evidence_ref)
    _compare_if_present(mismatches, "package_name", platform_snapshot.get("package_name"), package_manifest.get("package_name") or package_manifest.get("name"), evidence_ref)
    _compare_if_present(mismatches, "package_version", platform_snapshot.get("package_version"), package_manifest.get("package_version") or package_manifest.get("version"), evidence_ref)
    _compare_if_present(mismatches, "package_manifest_ref", platform_snapshot.get("package_manifest_ref"), package_manifest.get("manifest_ref"), evidence_ref)
    _compare_if_present(
        mismatches,
        "package_manifest_hash",
        platform_snapshot.get("package_manifest_hash"),
        package_manifest.get("package_manifest_hash") or package_manifest.get("manifest_hash"),
        evidence_ref,
    )
    _compare_if_present(mismatches, "lifecycle_phase", platform_snapshot.get("lifecycle_phase"), session.lifecycle_state, evidence_ref)
    _compare_if_present(mismatches, "reservation_lease_status", platform_snapshot.get("reservation_lease_status"), package_manifest.get("reservation_lease_status"), evidence_ref)
    if _snapshot_is_stale(platform_snapshot, generated_at=generated_at):
        mismatches.append(
            RunStateMismatch(
                "snapshot_staleness",
                str(platform_snapshot.get("stale_after") or platform_snapshot.get("stale") or ""),
                "fresh_required",
                evidence_ref,
            )
        )
    package_verdict = str(package_manifest.get("verdict") or "")
    snapshot_package_verdict = str(platform_snapshot.get("package_verdict") or "")
    if package_verdict and snapshot_package_verdict:
        _compare(mismatches, "package_verdict", snapshot_package_verdict, package_verdict, evidence_ref)
    local_hash = _stable_hash(session.to_dict())
    snapshot_hash = str(platform_snapshot.get("snapshot_hash") or _stable_hash(platform_snapshot))
    if mismatches:
        status = "BLOCKED"
        required_action = "emit_blocked"
        error_code = BLOCKED_STATE_DIVERGENCE
    else:
        status = "SYNCED"
        required_action = "continue"
        error_code = ""
    return RunStateReconciliation(
        reconciliation_id=f"run-state-reconciliation-{_stable_hash([local_hash, snapshot_hash, generated_at])[:12]}",
        schema_version=RECONCILIATION_SCHEMA_VERSION,
        generated_at=generated_at,
        run_id=str(platform_snapshot.get("run_id") or ""),
        local_state_hash=local_hash,
        platform_snapshot_id=str(platform_snapshot.get("snapshot_id") or ""),
        platform_snapshot_hash=snapshot_hash,
        status=status,
        mismatches=mismatches,
        required_action=required_action,
        error_code=error_code,
        evidence_refs=[evidence_ref] if evidence_ref else [],
        reconciliation_record_ref=f"run-state-reconciliation://{platform_snapshot.get('run_id') or 'unknown'}/{generated_at}",
    )


def _compare(mismatches: list[RunStateMismatch], field: str, platform_value: Any, local_value: Any, evidence_ref: str) -> None:
    platform_text = "" if platform_value is None else str(platform_value)
    local_text = "" if local_value is None else str(local_value)
    if platform_text != local_text:
        mismatches.append(RunStateMismatch(field, platform_text, local_text, evidence_ref))


def _compare_if_present(
    mismatches: list[RunStateMismatch],
    field: str,
    platform_value: Any,
    local_value: Any,
    evidence_ref: str,
) -> None:
    if platform_value in (None, "") and local_value in (None, ""):
        return
    _compare(mismatches, field, platform_value, local_value, evidence_ref)


def _active_value(values: list[str]) -> str:
    return values[-1] if values else ""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _snapshot_is_stale(platform_snapshot: dict[str, Any], *, generated_at: str) -> bool:
    if platform_snapshot.get("stale") is True:
        return True
    stale_after = str(platform_snapshot.get("stale_after") or "")
    if not stale_after:
        return False
    stale_at = _parse_iso(stale_after)
    generated = _parse_iso(generated_at)
    return stale_at is None or generated is None or stale_at <= generated


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
