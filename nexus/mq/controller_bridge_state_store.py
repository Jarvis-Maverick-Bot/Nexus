"""SQLite-backed persistence adapter for Track 2 controller bridge state."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from nexus.mq.controller_bridge_models import (
    AssignmentPublishRequest,
    DispatchEligibilityRequest,
    DispatchRun,
)
from nexus.mq.durable_state import DurableIdempotencyRecord, DurableStateStore
from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease


FAMILY_DISPATCH_RUN = "controller_bridge.dispatch_run"
FAMILY_ELIGIBILITY_REQUEST = "controller_bridge.eligibility_request"
FAMILY_LIFECYCLE_DECISION = "controller_bridge.lifecycle_decision"
FAMILY_RESERVATION_LEASE = "controller_bridge.reservation_lease"
FAMILY_ASSIGNMENT_PUBLISH = "controller_bridge.assignment_publish_request"
FAMILY_EVIDENCE_REF = "controller_bridge.evidence_ref"


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


def _payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return dict(value)
