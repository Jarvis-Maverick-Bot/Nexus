"""Dispatch-side Track 2 controller bridge orchestration.

This module validates and persists dispatch bridge records. It does not own
runtime registration/readiness/heartbeat, publish to MQ directly, or claim
business completion.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from nexus.mq.controller_bridge_models import (
    AssignmentPublishRequest,
    ControllerBridgeOperationResult,
    ControllerBridgePolicy,
    DispatchEligibilityRequest,
    DispatchRun,
    Layer1ApprovedDecision,
    RuntimeResultCandidate,
    decision_source_hash,
    dedupe,
    policy_hash,
    validate_layer1_decision,
)
from nexus.mq.controller_bridge_state_store import ControllerBridgeStateStore
from nexus.mq.eligibility_reservation_policy import validate_assignment_publish
from nexus.mq.runtime_lifecycle_controller import RuntimeEligibilityRequest


CANONICAL_ASSIGNMENT_NAMESPACE = "nexus.4_19.wbs7_19_15"
LEGACY_ASSIGNMENT_NAMESPACES = ("nexus.4_19.wbs7_19_14",)
ALLOWED_ASSIGNMENT_NAMESPACES = (CANONICAL_ASSIGNMENT_NAMESPACE, *LEGACY_ASSIGNMENT_NAMESPACES)
CANONICAL_ASSIGNMENT_AGENT_ID = "jarvis"


class ControllerBridgeDispatchController:
    def __init__(
        self,
        *,
        state_store: ControllerBridgeStateStore,
        policy: ControllerBridgePolicy | None = None,
    ) -> None:
        self.state_store = state_store
        self.policy = policy or ControllerBridgePolicy()

    def validate_intent(
        self,
        decision: Layer1ApprovedDecision | None,
        *,
        now_at: str,
    ) -> ControllerBridgeOperationResult:
        if decision is None:
            return ControllerBridgeOperationResult(False, "validate_intent", errors=["MISSING_DECISION"])
        errors = validate_layer1_decision(decision, now_at=now_at, policy=self.policy)
        return ControllerBridgeOperationResult(
            accepted=not errors,
            operation="validate_intent",
            errors=errors,
            payload={"source_hash": decision_source_hash(decision)} if not errors else {},
        )

    def create_run(
        self,
        *,
        decision: Layer1ApprovedDecision,
        dispatch_run_id: str,
        assignment_id: str,
        now_at: str,
    ) -> ControllerBridgeOperationResult:
        validation = self.validate_intent(decision, now_at=now_at)
        if not validation.accepted:
            return ControllerBridgeOperationResult(False, "create_run", errors=validation.errors)
        run = DispatchRun(
            dispatch_run_id=dispatch_run_id,
            decision_id=decision.decision_id,
            dispatch_packet_ref=decision.dispatch_packet_ref,
            source_hash=validation.payload["source_hash"],
            owner_principal_id=decision.owner_principal_id,
            target_agent_id=decision.target_agent_id,
            target_runtime_instance_id=decision.target_runtime_instance_id,
            target_runtime_role=decision.target_runtime_role,
            assignment_id=assignment_id,
            assignment_ttl_seconds=self.policy.assignment_ttl_seconds,
            idempotency_key=decision.idempotency_key,
            evidence_required=[item for item in decision.evidence_required if item != "controller.init"],
            status="source_bound",
            created_at=now_at,
            required_capability=decision.required_capability,
            required_authority_scope=decision.required_authority_scope,
            required_privacy_scope=decision.required_privacy_scope,
            allowed_task_boundary=decision.allowed_task_boundary,
            required_protocol_version=decision.required_protocol_version,
            no_go_scope=list(decision.no_go_scope),
            source_authority_ref=decision.decision_authority_ref,
        )
        self.state_store.record_dispatch_run(run)
        self.state_store.record_evidence_ref(dispatch_run_id, "dispatch", f"dispatch://run/{dispatch_run_id}")
        return ControllerBridgeOperationResult(True, "create_run", payload={"run": run})

    def request_eligibility(
        self,
        dispatch_run_id: str,
        *,
        runtime_lifecycle: Any,
        now_at: str,
    ) -> ControllerBridgeOperationResult:
        run = self.state_store.get_dispatch_run(dispatch_run_id)
        if run is None:
            return ControllerBridgeOperationResult(False, "request_eligibility", errors=["DISPATCH_RUN_NOT_FOUND"])
        request = DispatchEligibilityRequest(
            request_id=f"eligibility-{_digest(dispatch_run_id, run.assignment_id, run.idempotency_key)}",
            dispatch_run_id=run.dispatch_run_id,
            decision_id=run.decision_id,
            assignment_id=run.assignment_id,
            idempotency_key=run.idempotency_key,
            source_authority_ref=run.source_authority_ref,
            target_agent_id=run.target_agent_id,
            target_runtime_instance_id=run.target_runtime_instance_id,
            required_capability=run.required_capability,
            required_authority_scope=run.required_authority_scope,
            required_privacy_scope=run.required_privacy_scope,
            allowed_task_boundary=run.allowed_task_boundary,
            no_go_scope=list(run.no_go_scope),
            required_protocol_version=run.required_protocol_version,
            policy_hash=policy_hash(self.policy),
            assignment_ttl_seconds=run.assignment_ttl_seconds,
            evidence_required=list(run.evidence_required),
        )
        self.state_store.record_eligibility_request(request)
        runtime_request = RuntimeEligibilityRequest(
            request_id=request.request_id,
            dispatch_run_id=request.dispatch_run_id,
            assignment_id=request.assignment_id,
            idempotency_key=request.idempotency_key,
            source_authority_ref=request.source_authority_ref,
            target_agent_id=request.target_agent_id,
            target_runtime_instance_id=request.target_runtime_instance_id,
            required_capability=request.required_capability,
            required_authority_scope=request.required_authority_scope,
            required_privacy_scope=request.required_privacy_scope,
            allowed_task_boundary=request.allowed_task_boundary,
            no_go_scope=request.no_go_scope,
            required_protocol_version=request.required_protocol_version,
            policy_hash=request.policy_hash,
        )
        decision = runtime_lifecycle.query_eligibility(runtime_request, now_at=now_at)
        self.state_store.record_lifecycle_decision(decision)
        return ControllerBridgeOperationResult(
            accepted=decision.accepted,
            operation="request_eligibility",
            errors=list(decision.errors),
            payload={"eligibility_request": request, "lifecycle_decision": decision},
        )

    def publish_assignment(
        self,
        *,
        dispatch_run_id: str,
        assignment_id: str,
        lifecycle_decision_id: str,
        reservation_lease_id: str,
        runtime_instance_id: str,
        idempotency_key: str,
        subject: str,
        now_at: str,
    ) -> ControllerBridgeOperationResult:
        errors: list[str] = []
        run = self.state_store.get_dispatch_run(dispatch_run_id)
        if run is None:
            errors.append("DISPATCH_RUN_NOT_FOUND")
        else:
            if run.assignment_id != assignment_id:
                errors.append("ASSIGNMENT_ID_MISMATCH")
            if run.target_runtime_instance_id != runtime_instance_id:
                errors.append("RUNTIME_INSTANCE_ID_MISMATCH")
            if run.idempotency_key != idempotency_key:
                errors.append("IDEMPOTENCY_KEY_MISMATCH")
        replay = self.state_store.get_replay("publish", idempotency_key)
        if replay is not None and isinstance(replay.result_detail, dict):
            recorded = replay.result_detail
            if recorded.get("lifecycle_decision_id") != lifecycle_decision_id:
                errors.append("LIFECYCLE_DECISION_ID_MISMATCH")
            if recorded.get("reservation_lease_id") != reservation_lease_id:
                errors.append("RESERVATION_LEASE_ID_MISMATCH")
            if recorded.get("assignment_id") != assignment_id:
                errors.append("ASSIGNMENT_ID_MISMATCH")
        decision = self.state_store.get_lifecycle_decision(lifecycle_decision_id)
        lease = self.state_store.get_reservation_lease(reservation_lease_id)
        errors.extend(_subject_errors(subject, dispatch_run_id))
        validation = validate_assignment_publish(
            decision=decision,
            lease=lease,
            assignment_id=assignment_id,
            dispatch_run_id=dispatch_run_id,
            runtime_instance_id=runtime_instance_id,
            idempotency_key=idempotency_key,
            now_at=now_at,
        )
        if not validation.accepted:
            errors.extend(validation.errors)
        errors = dedupe(errors)
        if errors:
            return ControllerBridgeOperationResult(False, "publish_assignment", errors=errors)
        if replay is not None:
            request = AssignmentPublishRequest(**replay.result_detail["assignment_publish_request"])
            return ControllerBridgeOperationResult(
                True,
                "publish_assignment",
                errors=["DUPLICATE_ASSIGNMENT_SUPPRESSED"],
                payload={"assignment_publish_request": request},
                duplicate_suppressed=True,
            )
        assert run is not None
        request = AssignmentPublishRequest(
            assignment_id=assignment_id,
            dispatch_run_id=dispatch_run_id,
            dispatch_packet_ref=run.dispatch_packet_ref,
            decision_id=run.decision_id,
            lifecycle_decision_id=lifecycle_decision_id,
            reservation_lease_id=reservation_lease_id,
            runtime_instance_id=runtime_instance_id,
            idempotency_key=idempotency_key,
            subject=subject,
            assignment_ttl_seconds=run.assignment_ttl_seconds,
            evidence_required=list(run.evidence_required),
            requested_at=now_at,
        )
        self.state_store.record_assignment_publish_request(request)
        self.state_store.record_evidence_ref(dispatch_run_id, "assignment", f"assignment://{assignment_id}")
        self.state_store.record_replay(
            "publish",
            idempotency_key,
            message_id=f"publish-{_digest(assignment_id, reservation_lease_id, idempotency_key)}",
            result_detail={
                "assignment_id": assignment_id,
                "lifecycle_decision_id": lifecycle_decision_id,
                "reservation_lease_id": reservation_lease_id,
                "assignment_publish_request": request.to_dict(),
            },
        )
        return ControllerBridgeOperationResult(True, "publish_assignment", payload={"assignment_publish_request": request})

    def record_result_candidate(self, candidate: RuntimeResultCandidate) -> ControllerBridgeOperationResult:
        run = self.state_store.get_dispatch_run(candidate.dispatch_run_id)
        decision = self.state_store.get_lifecycle_decision(candidate.decision_id)
        lease = self.state_store.get_reservation_lease(candidate.lease_id)
        errors: list[str] = []
        if run is None:
            errors.append("DISPATCH_RUN_NOT_FOUND")
        else:
            if run.assignment_id != candidate.assignment_id:
                errors.append("RESULT_ASSIGNMENT_ID_MISMATCH")
            if run.target_runtime_instance_id != candidate.runtime_instance_id:
                errors.append("RESULT_RUNTIME_ID_MISMATCH")
        if decision is None:
            errors.append("MISSING_LIFECYCLE_DECISION")
        elif decision.dispatch_run_id != candidate.dispatch_run_id:
            errors.append("RESULT_DECISION_RUN_MISMATCH")
        if lease is None:
            errors.append("MISSING_RESERVATION_LEASE")
        elif lease.dispatch_run_id != candidate.dispatch_run_id:
            errors.append("RESULT_LEASE_RUN_MISMATCH")
        if candidate.not_business_completion is not True:
            errors.append("RESULT_CANDIDATE_CANNOT_BE_BUSINESS_COMPLETION")
        if not candidate.result_ref:
            errors.append("MISSING_RESULT_REF")
        if not candidate.evidence_refs:
            errors.append("MISSING_RESULT_EVIDENCE_REFS")
        if errors:
            return ControllerBridgeOperationResult(False, "result_candidate", errors=dedupe(errors))
        self.state_store.record_evidence_ref(candidate.dispatch_run_id, "result", candidate.result_ref)
        return ControllerBridgeOperationResult(True, "result_candidate", payload={"result_candidate": candidate})

    def cancel_or_drain(self, dispatch_run_id: str, *, reason_ref: str) -> ControllerBridgeOperationResult:
        if self.state_store.get_dispatch_run(dispatch_run_id) is None:
            return ControllerBridgeOperationResult(False, "cancel_or_drain", errors=["DISPATCH_RUN_NOT_FOUND"])
        if not reason_ref:
            return ControllerBridgeOperationResult(False, "cancel_or_drain", errors=["MISSING_DRAIN_REASON_REF"])
        self.state_store.record_evidence_ref(dispatch_run_id, "drain", reason_ref)
        return ControllerBridgeOperationResult(True, "cancel_or_drain", payload={"reason_ref": reason_ref})

    def collect_evidence(self, dispatch_run_id: str) -> ControllerBridgeOperationResult:
        if self.state_store.get_dispatch_run(dispatch_run_id) is None:
            return ControllerBridgeOperationResult(False, "collect_evidence", errors=["DISPATCH_RUN_NOT_FOUND"])
        refs = self.state_store.list_evidence_refs(dispatch_run_id)
        return ControllerBridgeOperationResult(True, "collect_evidence", payload={"evidence_refs": refs})


def _subject_errors(subject: str, dispatch_run_id: str) -> list[str]:
    errors: list[str] = []
    if not subject:
        errors.append("MISSING_PUBLISH_SUBJECT")
        return errors
    if "*" in subject or ">" in subject:
        errors.append("PUBLISH_SUBJECT_CANNOT_CONTAIN_WILDCARD")
    parts = subject.split(".")
    namespace_parts = _matching_namespace_parts(parts)
    if namespace_parts is None:
        namespace_parts = CANONICAL_ASSIGNMENT_NAMESPACE.split(".")
    expected_parts = namespace_parts + [dispatch_run_id, CANONICAL_ASSIGNMENT_AGENT_ID, "assignment"]
    if _is_runtime_scoped_assignment_alias(parts, dispatch_run_id):
        errors.append("PUBLISH_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY")
    elif parts != expected_parts:
        errors.append("PUBLISH_SUBJECT_MALFORMED")
    if parts[: len(namespace_parts)] != namespace_parts:
        errors.append("PUBLISH_SUBJECT_NAMESPACE_MISMATCH")
    run_index = len(namespace_parts)
    agent_index = run_index + 1
    if len(parts) <= run_index or parts[run_index] != dispatch_run_id:
        errors.append("PUBLISH_SUBJECT_RUN_MISMATCH")
    if len(parts) <= agent_index or parts[agent_index] != CANONICAL_ASSIGNMENT_AGENT_ID:
        errors.append("PUBLISH_SUBJECT_AGENT_MISMATCH")
    return dedupe(errors)


def _is_runtime_scoped_assignment_alias(parts: list[str], dispatch_run_id: str) -> bool:
    namespace_parts = _matching_namespace_parts(parts)
    if namespace_parts is None:
        return False
    return (
        len(parts) == len(namespace_parts) + 4
        and parts[len(namespace_parts)] == dispatch_run_id
        and parts[len(namespace_parts) + 1] == CANONICAL_ASSIGNMENT_AGENT_ID
        and bool(parts[len(namespace_parts) + 2])
        and parts[-1] == "assignment"
    )


def _matching_namespace_parts(parts: list[str]) -> list[str] | None:
    for namespace in ALLOWED_ASSIGNMENT_NAMESPACES:
        namespace_parts = namespace.split(".")
        if parts[: len(namespace_parts)] == namespace_parts:
            return namespace_parts
    return None


def _digest(*parts: str) -> str:
    return sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
