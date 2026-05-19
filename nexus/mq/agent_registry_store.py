"""Agent registry persistence boundary for WBS 7.8 Phase A.

The store boundary is intentionally separate from live runtime state. The fake
store below is deterministic and local-test only; it models normalized registry
columns plus a versioned JSON payload without becoming a live shared registry.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from nexus.mq.agent_registry import AgentRegistryRecord, validate_agent_registry_record
from nexus.mq.agent_registry_events import (
    AgentRegistryEvent,
    build_registry_event,
    secret_material_errors,
    validate_registry_event,
)


REGISTRY_RECORD_SCHEMA_VERSION = "4.19.registry.v1"
STORE_REVISION = 1


@dataclass
class StoredAgentRegistryRecord:
    record: AgentRegistryRecord
    revision: int
    normalized: dict[str, Any]


@dataclass
class AgentRegistryWriteResult:
    accepted: bool
    record: Optional[AgentRegistryRecord] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    event: Optional[AgentRegistryEvent] = None


@dataclass
class AgentRegistryReadResult:
    accepted: bool
    record: Optional[AgentRegistryRecord] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    row_quarantined: bool = False


@dataclass
class AgentRegistryLoadResult:
    records: list[StoredAgentRegistryRecord] = field(default_factory=list)
    rejected_agents: dict[str, list[str]] = field(default_factory=dict)
    store_errors: list[str] = field(default_factory=list)
    store_fail_closed: bool = False

    @property
    def accepted(self) -> bool:
        return not self.store_fail_closed


class AgentRegistryStore(Protocol):
    @property
    def authoritative(self) -> bool:
        ...

    def upsert_record(
        self,
        record: AgentRegistryRecord,
        *,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        ...

    def get_record(self, agent_id: str, *, now_at: Optional[str] = None) -> AgentRegistryReadResult:
        ...

    def load_records(self, *, now_at: Optional[str] = None) -> AgentRegistryLoadResult:
        ...

    def quarantine_record(
        self,
        agent_id: str,
        *,
        reason: str,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        ...

    def update_presence(
        self,
        agent_id: str,
        *,
        runtime_instance_id: str,
        presence_state: str,
        heartbeat_at: str,
        heartbeat_sequence: Optional[int],
        expected_revision: int,
        load_score: float = 0.0,
        accepting_new_work: bool = True,
        evidence_refs: Optional[list[str]] = None,
        health_summary_ref: Optional[str] = None,
        event_type: str = "heartbeat_accepted",
        now_at: Optional[str] = None,
        allow_lifecycle_downgrade: bool = False,
    ) -> AgentRegistryWriteResult:
        ...

    def get_heartbeat_sequence(self, agent_id: str) -> Optional[int]:
        ...

    def list_events(self) -> list[AgentRegistryEvent]:
        ...


class FakeAgentRegistryStore:
    """Deterministic store used for Phase A tests.

    `authoritative=False` models local cache/checkpoint data. Cache rows may be
    inspected in tests, but registry truth reads fail closed.
    """

    def __init__(self, *, authoritative: bool = True):
        self._authoritative = authoritative
        self._rows: dict[str, dict[str, Any]] = {}
        self._events: list[AgentRegistryEvent] = []
        self._store_corrupted = False

    @property
    def authoritative(self) -> bool:
        return self._authoritative

    def upsert_record(
        self,
        record: AgentRegistryRecord,
        *,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        store_errors = self._store_preflight_errors()
        if store_errors:
            return self._rejected_write(
                event_type="registry_store_load_failed",
                agent_id=record.agent_id,
                runtime_instance_id=record.runtime_instance_id,
                revision=None,
                errors=store_errors,
            )

        validation_errors = _validate_record_for_persistence(record, now_at=now_at)
        if validation_errors:
            return self._rejected_write(
                event_type="registry_record_rejected",
                agent_id=record.agent_id,
                runtime_instance_id=record.runtime_instance_id,
                revision=None,
                errors=validation_errors,
            )

        existing = self._rows.get(record.agent_id)
        if existing is not None:
            existing_read = self._row_to_record(existing, now_at=now_at)
            if not existing_read.accepted or existing_read.record is None:
                return self._rejected_write(
                    event_type="registry_record_rejected",
                    agent_id=record.agent_id,
                    runtime_instance_id=record.runtime_instance_id,
                    revision=existing.get("revision"),
                    errors=existing_read.errors,
                )
            current_revision = existing["revision"]
            current_record = existing_read.record
            if expected_revision is not None and expected_revision != current_revision:
                return self._rejected_write(
                    event_type="registry_record_rejected",
                    agent_id=record.agent_id,
                    runtime_instance_id=record.runtime_instance_id,
                    revision=current_revision,
                    errors=["STALE_REVISION"],
                )
            if current_record.runtime_instance_id != record.runtime_instance_id:
                return self._rejected_write(
                    event_type="registry_record_rejected",
                    agent_id=record.agent_id,
                    runtime_instance_id=record.runtime_instance_id,
                    revision=current_revision,
                    errors=["RUNTIME_INSTANCE_CONFLICT"],
                )
            if current_record.to_dict() == record.to_dict():
                event = self._append_event(
                    event_type="registry_record_unchanged",
                    agent_id=record.agent_id,
                    runtime_instance_id=record.runtime_instance_id,
                    revision=current_revision,
                    payload={"idempotent_refresh": True},
                )
                return AgentRegistryWriteResult(
                    accepted=True,
                    record=current_record,
                    revision=current_revision,
                    event=event,
                )
            new_revision = current_revision + 1
        else:
            if expected_revision not in (None, 0):
                return self._rejected_write(
                    event_type="registry_record_rejected",
                    agent_id=record.agent_id,
                    runtime_instance_id=record.runtime_instance_id,
                    revision=None,
                    errors=["STALE_REVISION"],
                )
            new_revision = 1

        row = record_to_normalized_row(record, revision=new_revision)
        self._rows[record.agent_id] = row
        event = self._append_event(
            event_type="registry_record_upserted",
            agent_id=record.agent_id,
            runtime_instance_id=record.runtime_instance_id,
            revision=new_revision,
            payload={"registry_status": record.registry_status, "initialization_status": record.initialization_status},
        )
        return AgentRegistryWriteResult(
            accepted=True,
            record=deepcopy(record),
            revision=new_revision,
            event=event,
        )

    def get_record(self, agent_id: str, *, now_at: Optional[str] = None) -> AgentRegistryReadResult:
        store_errors = self._store_preflight_errors()
        if store_errors:
            return AgentRegistryReadResult(accepted=False, errors=store_errors)
        row = self._rows.get(agent_id)
        if row is None:
            return AgentRegistryReadResult(accepted=False, errors=["REGISTRY_RECORD_NOT_FOUND"])
        return self._row_to_record(row, now_at=now_at)

    def load_records(self, *, now_at: Optional[str] = None) -> AgentRegistryLoadResult:
        store_errors = self._store_preflight_errors()
        if store_errors:
            self._append_event(
                event_type="registry_store_load_failed",
                agent_id=None,
                runtime_instance_id=None,
                revision=None,
                payload={"errors": list(store_errors)},
            )
            return AgentRegistryLoadResult(store_errors=store_errors, store_fail_closed=True)

        result = AgentRegistryLoadResult()
        for agent_id, row in sorted(self._rows.items()):
            read = self._row_to_record(row, now_at=now_at)
            if not read.accepted or read.record is None or read.revision is None:
                result.rejected_agents[agent_id] = read.errors
                continue
            result.records.append(
                StoredAgentRegistryRecord(
                    record=read.record,
                    revision=read.revision,
                    normalized=normalized_columns(row),
                )
            )
        return result

    def quarantine_record(
        self,
        agent_id: str,
        *,
        reason: str,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        read = self.get_record(agent_id, now_at=now_at)
        if not read.accepted or read.record is None:
            return self._rejected_write(
                event_type="registry_record_rejected",
                agent_id=agent_id,
                runtime_instance_id=None,
                revision=read.revision,
                errors=read.errors,
            )
        if expected_revision is not None and expected_revision != read.revision:
            return self._rejected_write(
                event_type="registry_record_rejected",
                agent_id=agent_id,
                runtime_instance_id=read.record.runtime_instance_id,
                revision=read.revision,
                errors=["STALE_REVISION"],
            )
        quarantined = deepcopy(read.record)
        quarantined.initialization_status = "quarantined"
        quarantined.presence_state = "offline"
        quarantined.accepting_new_work = False
        quarantined.readiness_blocker = reason
        quarantined.updated_at = now_at or _now_iso()
        revision = (read.revision or 0) + 1
        self._rows[agent_id] = record_to_normalized_row(quarantined, revision=revision, quarantined=True)
        event = self._append_event(
            event_type="registry_record_quarantined",
            agent_id=agent_id,
            runtime_instance_id=quarantined.runtime_instance_id,
            revision=revision,
            payload={"reason": reason},
        )
        return AgentRegistryWriteResult(
            accepted=True,
            record=quarantined,
            revision=revision,
            event=event,
        )

    def update_presence(
        self,
        agent_id: str,
        *,
        runtime_instance_id: str,
        presence_state: str,
        heartbeat_at: str,
        heartbeat_sequence: Optional[int],
        expected_revision: int,
        load_score: float = 0.0,
        accepting_new_work: bool = True,
        evidence_refs: Optional[list[str]] = None,
        health_summary_ref: Optional[str] = None,
        event_type: str = "heartbeat_accepted",
        now_at: Optional[str] = None,
        allow_lifecycle_downgrade: bool = False,
    ) -> AgentRegistryWriteResult:
        store_errors = self._store_preflight_errors()
        if store_errors:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=None,
                errors=store_errors,
            )
        row = self._rows.get(agent_id)
        if row is None:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=None,
                errors=["REGISTRY_RECORD_NOT_FOUND"],
            )
        if row.get("revision") != expected_revision:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=["STALE_REVISION"],
            )
        existing_read = self._row_to_record(row, now_at=now_at)
        if not existing_read.accepted or existing_read.record is None:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=existing_read.errors,
            )
        record = existing_read.record
        if record.runtime_instance_id != runtime_instance_id:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=["RUNTIME_INSTANCE_MISMATCH"],
            )
        if record.registry_status in {"suspended", "revoked"}:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=[f"REGISTRY_NOT_ACTIVE: {record.registry_status}"],
            )
        previous_sequence = row.get("heartbeat_sequence")
        if heartbeat_sequence is not None and previous_sequence is not None and heartbeat_sequence <= previous_sequence:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=["STALE_HEARTBEAT_SEQUENCE"],
            )
        if not 0 <= load_score <= 1:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=["INVALID_HEARTBEAT_LOAD_SCORE"],
            )
        if presence_state not in {"online", "idle", "busy", "degraded", "draining", "offline", "stale"}:
            return self._rejected_write(
                event_type="heartbeat_rejected",
                agent_id=agent_id,
                runtime_instance_id=runtime_instance_id,
                revision=row.get("revision"),
                errors=[f"INVALID_PRESENCE_STATE: {presence_state}"],
            )

        updated = deepcopy(record)
        updated.presence_state = presence_state
        updated.last_heartbeat_at = heartbeat_at
        updated.load_score = load_score
        updated.accepting_new_work = accepting_new_work and presence_state == "idle"
        updated.updated_at = heartbeat_at
        revision = expected_revision + 1
        updated_row = record_to_normalized_row(updated, revision=revision, quarantined=bool(row.get("quarantined", False)))
        updated_row["heartbeat_sequence"] = heartbeat_sequence if heartbeat_sequence is not None else previous_sequence
        updated_row["heartbeat_evidence_refs"] = list(evidence_refs or [])
        updated_row["health_summary_ref"] = health_summary_ref
        self._rows[agent_id] = updated_row
        event = self._append_event(
            event_type=event_type,
            agent_id=agent_id,
            runtime_instance_id=runtime_instance_id,
            revision=revision,
            payload={
                "presence_state": presence_state,
                "heartbeat_sequence": updated_row["heartbeat_sequence"],
                "heartbeat_at": heartbeat_at,
                "accepting_new_work": updated.accepting_new_work,
                "health_summary_ref": health_summary_ref,
            },
        )
        return AgentRegistryWriteResult(
            accepted=True,
            record=updated,
            revision=revision,
            event=event,
        )

    def get_heartbeat_sequence(self, agent_id: str) -> Optional[int]:
        row = self._rows.get(agent_id)
        if row is None:
            return None
        sequence = row.get("heartbeat_sequence")
        return sequence if isinstance(sequence, int) else None

    def list_events(self) -> list[AgentRegistryEvent]:
        return list(self._events)

    def normalized_row(self, agent_id: str) -> Optional[dict[str, Any]]:
        row = self._rows.get(agent_id)
        return deepcopy(row) if row is not None else None

    def seed_raw_row(self, row: dict[str, Any]) -> None:
        agent_id = row.get("agent_id")
        if not agent_id:
            raise ValueError("seed row requires agent_id")
        self._rows[str(agent_id)] = deepcopy(row)

    def corrupt_store_for_test(self) -> None:
        self._store_corrupted = True

    def _store_preflight_errors(self) -> list[str]:
        errors: list[str] = []
        if self._store_corrupted:
            errors.append("REGISTRY_STORE_CORRUPTED")
        if not self._authoritative:
            errors.append("REGISTRY_TRUTH_UNVERIFIED")
        return errors

    def _row_to_record(self, row: dict[str, Any], *, now_at: Optional[str]) -> AgentRegistryReadResult:
        row_errors = _validate_row_shape(row)
        if row_errors:
            return AgentRegistryReadResult(accepted=False, errors=row_errors, row_quarantined=True)
        try:
            record_payload = deepcopy(row["payload"]["record"])
            record = AgentRegistryRecord(**record_payload)
        except (KeyError, TypeError, ValueError) as exc:
            return AgentRegistryReadResult(
                accepted=False,
                errors=[f"MALFORMED_REGISTRY_ROW: {exc.__class__.__name__}"],
                row_quarantined=True,
            )
        validation_errors = _validate_record_for_persistence(record, now_at=now_at)
        normalized_errors = _validate_normalized_matches_record(row, record)
        errors = validation_errors + normalized_errors
        if errors:
            return AgentRegistryReadResult(
                accepted=False,
                record=record,
                revision=row.get("revision"),
                errors=errors,
                row_quarantined=True,
            )
        return AgentRegistryReadResult(
            accepted=True,
            record=record,
            revision=row["revision"],
            row_quarantined=bool(row.get("quarantined", False)),
        )

    def _append_event(
        self,
        *,
        event_type: str,
        agent_id: Optional[str],
        runtime_instance_id: Optional[str],
        revision: Optional[int],
        payload: Optional[dict[str, Any]] = None,
    ) -> AgentRegistryEvent:
        event = build_registry_event(
            event_type=event_type,
            agent_id=agent_id,
            runtime_instance_id=runtime_instance_id,
            revision=revision,
            payload=payload,
        )
        validation = validate_registry_event(event)
        if validation.valid:
            self._events.append(event)
        else:
            self._events.append(
                build_registry_event(
                    event_type="registry_store_load_failed",
                    agent_id=agent_id,
                    runtime_instance_id=runtime_instance_id,
                    revision=revision,
                    payload={"event_validation_errors": validation.errors},
                )
            )
        return event

    def _rejected_write(
        self,
        *,
        event_type: str,
        agent_id: Optional[str],
        runtime_instance_id: Optional[str],
        revision: Optional[int],
        errors: list[str],
    ) -> AgentRegistryWriteResult:
        event = self._append_event(
            event_type=event_type,
            agent_id=agent_id,
            runtime_instance_id=runtime_instance_id,
            revision=revision,
            payload={"errors": list(errors)},
        )
        return AgentRegistryWriteResult(accepted=False, revision=revision, errors=list(errors), event=event)


def record_to_normalized_row(
    record: AgentRegistryRecord,
    *,
    revision: int,
    quarantined: bool = False,
) -> dict[str, Any]:
    payload = {
        "schema_version": REGISTRY_RECORD_SCHEMA_VERSION,
        "record": record.to_dict(),
        "not_business_completion": True,
    }
    return {
        "schema_version": REGISTRY_RECORD_SCHEMA_VERSION,
        "store_revision": STORE_REVISION,
        "agent_id": record.agent_id,
        "runtime_instance_id": record.runtime_instance_id,
        "role": record.role,
        "owner_principal_id": record.owner_principal_id,
        "runtime_type": record.runtime_type,
        "registry_status": record.registry_status,
        "initialization_status": record.initialization_status,
        "presence_state": record.presence_state,
        "startup_packet_ref": record.startup_packet_ref,
        "readiness_evidence_ref": record.readiness_evidence_ref,
        "startup_packet_expires_at": record.startup_packet_expires_at,
        "heartbeat_ttl_seconds": record.heartbeat_ttl_seconds,
        "last_heartbeat_at": record.last_heartbeat_at,
        "updated_at": record.updated_at,
        "revision": revision,
        "payload_schema_version": REGISTRY_RECORD_SCHEMA_VERSION,
        "payload": payload,
        "quarantined": quarantined,
        "heartbeat_sequence": None,
        "heartbeat_evidence_refs": [],
        "health_summary_ref": None,
    }


def normalized_columns(row: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "schema_version",
        "store_revision",
        "agent_id",
        "runtime_instance_id",
        "role",
        "owner_principal_id",
        "runtime_type",
        "registry_status",
        "initialization_status",
        "presence_state",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "startup_packet_expires_at",
        "heartbeat_ttl_seconds",
        "last_heartbeat_at",
        "updated_at",
        "revision",
        "payload_schema_version",
        "quarantined",
        "heartbeat_sequence",
        "heartbeat_evidence_refs",
        "health_summary_ref",
    }
    return {key: deepcopy(row.get(key)) for key in sorted(keys)}


def _validate_record_for_persistence(record: AgentRegistryRecord, *, now_at: Optional[str]) -> list[str]:
    errors = validate_agent_registry_record(record)
    if record.not_business_completion is not True:
        errors.append("REGISTRY_RECORD_CANNOT_BE_BUSINESS_COMPLETION")
    errors.extend(secret_material_errors(record.to_dict(), path="record"))
    if record.startup_packet_expires_at:
        expires_dt = _parse_iso(record.startup_packet_expires_at)
        now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
        if expires_dt is None:
            errors.append("STARTUP_PACKET_FRESHNESS_INVALID")
        elif now_dt is None:
            errors.append("REGISTRY_TRUTH_TIME_UNVERIFIABLE")
        elif expires_dt <= now_dt:
            errors.append("STARTUP_PACKET_EXPIRED")
    if record.updated_at and _parse_iso(record.updated_at) is None:
        errors.append("REGISTRY_UPDATED_AT_INVALID")
    if record.last_heartbeat_at and _parse_iso(record.last_heartbeat_at) is None:
        errors.append("LAST_HEARTBEAT_AT_INVALID")
    return _dedupe(errors)


def _validate_row_shape(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_columns = [
        "schema_version",
        "store_revision",
        "agent_id",
        "runtime_instance_id",
        "registry_status",
        "initialization_status",
        "startup_packet_expires_at",
        "revision",
        "payload_schema_version",
        "payload",
    ]
    for column in required_columns:
        if column not in row:
            errors.append(f"MALFORMED_REGISTRY_ROW: missing {column}")
    if row.get("schema_version") != REGISTRY_RECORD_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_REGISTRY_SCHEMA: {row.get('schema_version')}")
    if row.get("payload_schema_version") != REGISTRY_RECORD_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_REGISTRY_PAYLOAD_SCHEMA: {row.get('payload_schema_version')}")
    if not isinstance(row.get("revision"), int) or row.get("revision", 0) <= 0:
        errors.append("MALFORMED_REGISTRY_ROW: invalid revision")
    payload = row.get("payload")
    if not isinstance(payload, dict):
        errors.append("MALFORMED_REGISTRY_ROW: payload not object")
    elif payload.get("schema_version") != REGISTRY_RECORD_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_REGISTRY_PAYLOAD_SCHEMA: {payload.get('schema_version')}")
    errors.extend(secret_material_errors(row, path="row"))
    return _dedupe(errors)


def _validate_normalized_matches_record(row: dict[str, Any], record: AgentRegistryRecord) -> list[str]:
    errors: list[str] = []
    for key in [
        "agent_id",
        "runtime_instance_id",
        "role",
        "owner_principal_id",
        "runtime_type",
        "registry_status",
        "initialization_status",
        "presence_state",
        "startup_packet_ref",
        "readiness_evidence_ref",
        "startup_packet_expires_at",
        "heartbeat_ttl_seconds",
        "last_heartbeat_at",
        "updated_at",
    ]:
        if row.get(key) != getattr(record, key):
            errors.append(f"NORMALIZED_PAYLOAD_MISMATCH: {key}")
    return errors


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
