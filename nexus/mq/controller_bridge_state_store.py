"""SQLite-backed persistence adapter for Track 2 controller bridge state."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from nexus.mq.controller_bridge_models import (
    AssignmentPublishRequest,
    CleanRunIdentity,
    DispatchEligibilityRequest,
    DispatchRun,
    DuplicateReplayPayload,
)
from nexus.mq.durable_state import DurableIdempotencyRecord, DurableStateStore
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease


FAMILY_DISPATCH_RUN = "controller_bridge.dispatch_run"
FAMILY_ELIGIBILITY_REQUEST = "controller_bridge.eligibility_request"
FAMILY_LIFECYCLE_DECISION = "controller_bridge.lifecycle_decision"
FAMILY_RESERVATION_LEASE = "controller_bridge.reservation_lease"
FAMILY_ASSIGNMENT_PUBLISH = "controller_bridge.assignment_publish_request"
FAMILY_EVIDENCE_REF = "controller_bridge.evidence_ref"
FAMILY_DUPLICATE_REPLAY = "controller_bridge.duplicate_replay_payload"
FAMILY_CLEAN_RUN_IDENTITY = "controller_bridge.clean_run_identity"
FAMILY_RUN_STATE_SNAPSHOT = "controller_bridge.run_state_snapshot"


class ControllerBridgeStateStore:
    def __init__(self, durable_store: DurableStateStore):
        self.durable_store = durable_store

    def close(self) -> None:
        self.durable_store.close()

    def record_dispatch_run(self, run: DispatchRun) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_DISPATCH_RUN,
            run.status,
            _payload(run),
            workflow_instance_id=run.dispatch_run_id,
            target_ref=run.assignment_id,
            dedupe_key=run.dispatch_run_id,
            created_at=run.created_at,
        )

    def get_dispatch_run(self, dispatch_run_id: str) -> DispatchRun | None:
        record = self.durable_store.find_phase5_durable_record(FAMILY_DISPATCH_RUN, dispatch_run_id)
        if record is None:
            return None
        return DispatchRun(**record.payload)

    def record_eligibility_request(self, request: DispatchEligibilityRequest) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_ELIGIBILITY_REQUEST,
            "requested",
            _payload(request),
            workflow_instance_id=request.dispatch_run_id,
            target_ref=request.target_runtime_instance_id,
            dedupe_key=request.request_id,
        )

    def record_lifecycle_decision(self, decision: RuntimeEligibilityDecision) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_LIFECYCLE_DECISION,
            "allowed" if decision.accepted else "blocked",
            _payload(decision),
            workflow_instance_id=decision.dispatch_run_id,
            target_ref=decision.target_runtime_instance_id,
            dedupe_key=decision.decision_id,
        )

    def get_lifecycle_decision(self, decision_id: str) -> RuntimeEligibilityDecision | None:
        record = self.durable_store.find_phase5_durable_record(FAMILY_LIFECYCLE_DECISION, decision_id)
        if record is None:
            return None
        return RuntimeEligibilityDecision(**record.payload)

    def record_reservation_lease(self, lease: RuntimeReservationLease) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_RESERVATION_LEASE,
            lease.status,
            _payload(lease),
            workflow_instance_id=lease.dispatch_run_id,
            target_ref=lease.target_runtime_instance_id,
            dedupe_key=None,
        )

    def get_reservation_lease(self, lease_id: str) -> RuntimeReservationLease | None:
        matches = [
            record
            for record in self.durable_store.list_phase5_durable_records(family=FAMILY_RESERVATION_LEASE)
            if record.payload.get("lease_id") == lease_id
        ]
        if not matches:
            return None
        return RuntimeReservationLease(**matches[-1].payload)

    def record_assignment_publish_request(self, request: AssignmentPublishRequest) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_ASSIGNMENT_PUBLISH,
            "requested",
            _payload(request),
            workflow_instance_id=request.dispatch_run_id,
            target_ref=request.runtime_instance_id,
            dedupe_key=f"{request.assignment_id}:{request.reservation_lease_id}:{request.idempotency_key}",
            created_at=request.requested_at,
        )

    def record_evidence_ref(self, dispatch_run_id: str, evidence_type: str, evidence_ref: str) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_EVIDENCE_REF,
            evidence_type,
            {"dispatch_run_id": dispatch_run_id, "evidence_type": evidence_type, "evidence_ref": evidence_ref},
            workflow_instance_id=dispatch_run_id,
            target_ref=evidence_ref,
            dedupe_key=f"{dispatch_run_id}:{evidence_type}:{evidence_ref}",
        )

    def record_duplicate_replay_payload(self, payload: DuplicateReplayPayload) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_DUPLICATE_REPLAY,
            "validated",
            _payload(payload),
            workflow_instance_id=payload.dispatch_run_id,
            target_ref=payload.assignment_id,
            dedupe_key=payload.replay_id,
        )

    def record_clean_run_identity(self, identity: CleanRunIdentity, *, status: str) -> None:
        self.durable_store.create_phase5_durable_record(
            FAMILY_CLEAN_RUN_IDENTITY,
            status,
            _payload(identity),
            workflow_instance_id=identity.run_id,
            target_ref=identity.assignment_id,
            dedupe_key=_clean_run_tuple_key(identity),
        )

    def find_clean_run_identity(self, identity: CleanRunIdentity) -> CleanRunIdentity | None:
        record = self.durable_store.find_phase5_durable_record(
            FAMILY_CLEAN_RUN_IDENTITY,
            _clean_run_tuple_key(identity),
        )
        if record is None:
            return None
        return CleanRunIdentity(**record.payload)

    def record_run_state_snapshot(self, snapshot: Any) -> None:
        payload = _payload(snapshot)
        self.durable_store.create_phase5_durable_record(
            FAMILY_RUN_STATE_SNAPSHOT,
            str(payload.get("local_state_verdict") or payload.get("status") or "snapshot"),
            payload,
            workflow_instance_id=str(payload.get("run_id") or payload.get("dispatch_run_id") or ""),
            target_ref=str(payload.get("assignment_id") or payload.get("snapshot_id") or ""),
            dedupe_key=str(payload.get("snapshot_id") or ""),
            created_at=str(payload.get("observed_at") or payload.get("created_at") or ""),
        )

    def get_run_state_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        record = self.durable_store.find_phase5_durable_record(FAMILY_RUN_STATE_SNAPSHOT, snapshot_id)
        return None if record is None else dict(record.payload)

    def query_run_state_snapshots(
        self,
        *,
        snapshot_id: str | None = None,
        run_id: str | None = None,
        wbs_ref: str | None = None,
        assignment_id: str | None = None,
        package_name: str | None = None,
    ) -> list[dict[str, Any]]:
        records = self.durable_store.list_phase5_durable_records(family=FAMILY_RUN_STATE_SNAPSHOT)
        snapshots = [dict(record.payload) for record in records]
        filters = {
            "snapshot_id": snapshot_id,
            "run_id": run_id,
            "wbs_ref": wbs_ref,
            "assignment_id": assignment_id,
            "package_name": package_name,
        }
        for field_name, expected in filters.items():
            if expected is not None:
                snapshots = [snapshot for snapshot in snapshots if str(snapshot.get(field_name) or "") == expected]
        return snapshots

    def latest_run_state_snapshot(
        self,
        *,
        run_id: str | None = None,
        wbs_ref: str | None = None,
        assignment_id: str | None = None,
        package_name: str | None = None,
    ) -> dict[str, Any] | None:
        snapshots = self.query_run_state_snapshots(
            run_id=run_id,
            wbs_ref=wbs_ref,
            assignment_id=assignment_id,
            package_name=package_name,
        )
        if not snapshots:
            return None
        return sorted(
            snapshots,
            key=lambda snapshot: (
                str(snapshot.get("observed_at") or ""),
                str(snapshot.get("created_at") or ""),
                str(snapshot.get("snapshot_id") or ""),
            ),
        )[-1]

    def list_evidence_refs(self, dispatch_run_id: str) -> list[str]:
        return [
            record.payload["evidence_ref"]
            for record in self.durable_store.list_phase5_durable_records(
                family=FAMILY_EVIDENCE_REF,
                workflow_instance_id=dispatch_run_id,
            )
        ]

    def record_replay(
        self,
        operation: str,
        idempotency_key: str,
        message_id: str,
        result_detail: dict[str, Any],
    ) -> DurableIdempotencyRecord:
        return self.durable_store.record_idempotency(
            _replay_key(operation, idempotency_key),
            message_id=message_id,
            workflow_id=f"controller_bridge:{operation}",
            state="completed",
            result_detail=result_detail,
        )

    def get_replay(self, operation: str, idempotency_key: str) -> DurableIdempotencyRecord | None:
        return self.durable_store.get_idempotency(_replay_key(operation, idempotency_key))


def _replay_key(operation: str, idempotency_key: str) -> str:
    return f"controller_bridge:{operation}:{idempotency_key}"


def _clean_run_tuple_key(identity: CleanRunIdentity) -> str:
    return "|".join(
        [
            identity.wbs_ref,
            identity.run_id,
            identity.dispatch_run_id,
            identity.assignment_id,
            identity.idempotency_key,
            identity.lifecycle_decision_id,
            identity.reservation_lease_id,
            identity.runtime_instance_id,
            identity.package_name,
            identity.package_version,
            identity.source_authority_hash,
        ]
    )


def _payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return dict(value)
