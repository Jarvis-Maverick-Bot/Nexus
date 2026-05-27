"""Module CLI for Track 2 controller bridge deterministic tests."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass, replace
from datetime import timedelta
import json
from pathlib import Path
from typing import Any, Optional

from nexus.mq.controller_bridge_dispatch import ControllerBridgeDispatchController
from nexus.mq.controller_bridge_models import Layer1ApprovedDecision, parse_iso
from nexus.mq.controller_bridge_state_store import ControllerBridgeStateStore
from nexus.mq.durable_state import DurableStateStore
from nexus.mq.eligibility_reservation_policy import (
    RuntimeEligibilityDecision,
    RuntimeReservationLease,
    release_reservation_lease,
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nexus.mq.controller_bridge_cli")
    subparsers = parser.add_subparsers(dest="plane", required=True)
    _add_dispatch_parser(subparsers)
    _add_runtime_parser(subparsers)
    args = parser.parse_args(argv)
    try:
        result = _dispatch(args)
    except Exception as exc:
        _emit({"accepted": False, "errors": [str(exc)]})
        return 1
    _emit(_json_safe(result))
    return 0 if result.get("accepted", False) else 1


def _add_dispatch_parser(subparsers: argparse._SubParsersAction) -> None:
    dispatch = subparsers.add_parser("dispatch")
    commands = dispatch.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--decision-json", required=True)
    validate.add_argument("--now-at", required=True)
    create = commands.add_parser("create")
    create.add_argument("--state-db", required=True)
    create.add_argument("--decision-json", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--assignment-id", required=True)
    create.add_argument("--now-at", required=True)
    request_eligibility = commands.add_parser("request-eligibility")
    request_eligibility.add_argument("--state-db", required=True)
    request_eligibility.add_argument("--run-id", required=True)
    request_eligibility.add_argument("--lifecycle-decision-json", required=True)
    request_eligibility.add_argument("--now-at", required=True)
    publish = commands.add_parser("publish-assignment")
    publish.add_argument("--state-db", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--assignment-id", required=True)
    publish.add_argument("--decision-id", required=True)
    publish.add_argument("--lease-id", required=True)
    publish.add_argument("--runtime-instance-id", required=True)
    publish.add_argument("--idempotency-key", required=True)
    publish.add_argument("--subject", required=True)
    publish.add_argument("--now-at", required=True)
    status = commands.add_parser("status")
    status.add_argument("--state-db", required=True)
    status.add_argument("--run-id", required=True)
    drain = commands.add_parser("drain")
    drain.add_argument("--state-db", required=True)
    drain.add_argument("--run-id", required=True)
    drain.add_argument("--reason-ref", required=True)
    evidence = commands.add_parser("evidence")
    evidence.add_argument("--state-db", required=True)
    evidence.add_argument("--run-id", required=True)


def _add_runtime_parser(subparsers: argparse._SubParsersAction) -> None:
    runtime = subparsers.add_parser("runtime")
    commands = runtime.add_subparsers(dest="command", required=True)
    eligibility = commands.add_parser("eligibility")
    eligibility.add_argument("--state-db", required=True)
    eligibility.add_argument("--decision-json", required=True)
    reserve = commands.add_parser("reserve")
    reserve.add_argument("--state-db", required=True)
    reserve.add_argument("--decision-id", required=True)
    reserve.add_argument("--lease-id", required=True)
    reserve.add_argument("--now-at", required=True)
    lease_status = commands.add_parser("lease-status")
    lease_status.add_argument("--state-db", required=True)
    lease_status.add_argument("--lease-id", required=True)
    lease_status.add_argument("--now-at", required=False)
    release = commands.add_parser("release")
    release.add_argument("--state-db", required=True)
    release.add_argument("--lease-id", required=True)
    release.add_argument("--reason-ref", required=True)
    release.add_argument("--now-at", required=True)
    metrics = commands.add_parser("metrics")
    metrics.add_argument("--state-db", required=True)


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.plane == "dispatch":
        if args.command == "validate":
            store = ControllerBridgeStateStore(DurableStateStore(":memory:"))
            controller = ControllerBridgeDispatchController(state_store=store)
            return controller.validate_intent(_layer1_decision(args.decision_json), now_at=args.now_at).to_dict()
        controller = _controller(args.state_db)
        if args.command == "create":
            return controller.create_run(
                decision=_layer1_decision(args.decision_json),
                dispatch_run_id=args.run_id,
                assignment_id=args.assignment_id,
                now_at=args.now_at,
            ).to_dict()
        if args.command == "request-eligibility":
            provider = _StaticRuntimeLifecycleProvider(
                RuntimeEligibilityDecision(**_read_json(args.lifecycle_decision_json))
            )
            result = controller.request_eligibility(
                args.run_id,
                runtime_lifecycle=provider,
                now_at=args.now_at,
            ).to_dict()
            result["payload"]["runtime_lifecycle_provider"] = provider.to_dict()
            return result
        if args.command == "publish-assignment":
            return controller.publish_assignment(
                dispatch_run_id=args.run_id,
                assignment_id=args.assignment_id,
                lifecycle_decision_id=args.decision_id,
                reservation_lease_id=args.lease_id,
                runtime_instance_id=args.runtime_instance_id,
                idempotency_key=args.idempotency_key,
                subject=args.subject,
                now_at=args.now_at,
            ).to_dict()
        if args.command == "status":
            run = controller.state_store.get_dispatch_run(args.run_id)
            return {"accepted": run is not None, "payload": {"run": run}}
        if args.command == "drain":
            return controller.cancel_or_drain(args.run_id, reason_ref=args.reason_ref).to_dict()
        if args.command == "evidence":
            return controller.collect_evidence(args.run_id).to_dict()
    store = ControllerBridgeStateStore(DurableStateStore(str(args.state_db)))
    if args.command == "eligibility":
        decision = RuntimeEligibilityDecision(**_read_json(args.decision_json))
        store.record_lifecycle_decision(decision)
        return {"accepted": decision.accepted, "payload": {"decision": decision}}
    if args.command == "reserve":
        decision = store.get_lifecycle_decision(args.decision_id)
        if decision is None:
            return {"accepted": False, "errors": ["LIFECYCLE_DECISION_NOT_FOUND"]}
        lease = _lease_from_decision(decision, lease_id=args.lease_id, now_at=args.now_at)
        store.record_reservation_lease(lease)
        return {"accepted": True, "payload": {"lease": lease}}
    if args.command == "lease-status":
        lease = store.get_reservation_lease(args.lease_id)
        if lease is None:
            return {"accepted": False, "errors": ["RESERVATION_LEASE_NOT_FOUND"]}
        return {"accepted": True, "payload": {"lease": lease}}
    if args.command == "release":
        lease = store.get_reservation_lease(args.lease_id)
        if lease is None:
            return {"accepted": False, "errors": ["RESERVATION_LEASE_NOT_FOUND"]}
        released = release_reservation_lease(lease, released_at=args.now_at, reason_ref=args.reason_ref)
        store.record_reservation_lease(released)
        return {"accepted": True, "payload": {"lease": released}}
    if args.command == "metrics":
        return {"accepted": True, "payload": {"runtime_metrics": {"source": "controller_bridge_state_store"}}}
    return {"accepted": False, "errors": ["UNKNOWN_COMMAND"]}


def _controller(state_db: str) -> ControllerBridgeDispatchController:
    return ControllerBridgeDispatchController(
        state_store=ControllerBridgeStateStore(DurableStateStore(str(state_db))),
    )


def _layer1_decision(path: str) -> Layer1ApprovedDecision:
    return Layer1ApprovedDecision(**_read_json(path))


def _read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _lease_from_decision(decision: RuntimeEligibilityDecision, *, lease_id: str, now_at: str) -> RuntimeReservationLease:
    now = parse_iso(now_at)
    expires_at = (now + timedelta(seconds=60)).isoformat() if now is not None else ""
    release_required_by = (now + timedelta(seconds=15)).isoformat() if now is not None else ""
    return RuntimeReservationLease(
        lease_id=lease_id,
        lifecycle_decision_id=decision.decision_id,
        assignment_id=decision.assignment_id,
        dispatch_run_id=decision.dispatch_run_id,
        target_runtime_instance_id=decision.target_runtime_instance_id,
        active=True,
        status="active",
        expires_at=expires_at,
        policy_hash=decision.policy_hash,
        idempotency_key=decision.idempotency_key,
        release_required_by=release_required_by,
        runtime_role=decision.runtime_role,
        runtime_owner=decision.runtime_owner,
    )


class _StaticRuntimeLifecycleProvider:
    def __init__(self, decision: RuntimeEligibilityDecision) -> None:
        self.decision = decision
        self.query_calls = 0
        self.mutating_calls: list[str] = []

    def query_eligibility(self, request: Any, *, now_at: str) -> RuntimeEligibilityDecision:
        self.query_calls += 1
        mismatches: list[str] = []
        expected = {
            "request_id": request.request_id,
            "dispatch_run_id": request.dispatch_run_id,
            "assignment_id": request.assignment_id,
            "idempotency_key": request.idempotency_key,
            "target_agent_id": request.target_agent_id,
            "target_runtime_instance_id": request.target_runtime_instance_id,
            "policy_hash": request.policy_hash,
        }
        for field_name, expected_value in expected.items():
            if getattr(self.decision, field_name) != expected_value:
                mismatches.append(f"LIFECYCLE_DECISION_{field_name.upper()}_MISMATCH")
        if mismatches:
            return replace(
                self.decision,
                accepted=False,
                errors=list(self.decision.errors) + mismatches,
            )
        return self.decision

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": "static_lifecycle_decision_json",
            "query_calls": self.query_calls,
            "mutating_calls": list(self.mutating_calls),
        }


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(_json_safe(payload), sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
