"""Default-off resident controller service shell."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.mq.resident_controller.config import validate_resident_controller_config
from nexus.mq.resident_controller.evidence import ResidentEvidenceRecord


@dataclass
class ResidentControllerServicePolicy:
    default_enabled: bool = False
    uat_authorized: bool = False


@dataclass
class BrokerReadinessSnapshot:
    connected: bool
    subscriptions_ready: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


@dataclass
class ResidentControllerStartDecision:
    accepted: bool
    daemon_started: bool = False
    service_state: str = "blocked"
    evidence_records: list[ResidentEvidenceRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


class ResidentControllerService:
    def __init__(self, *, policy: ResidentControllerServicePolicy):
        self.policy = policy

    def evaluate_start(self, *, run_authorization_ref: str) -> ResidentControllerStartDecision:
        errors: list[str] = []
        if not self.policy.default_enabled:
            errors.append("RESIDENT_CONTROLLER_DEFAULT_OFF")
        if not run_authorization_ref:
            errors.append("MISSING_UAT_AUTHORIZATION")
        if not self.policy.uat_authorized:
            errors.append("UAT_AUTHORIZATION_REQUIRED")
        if errors:
            return ResidentControllerStartDecision(False, daemon_started=False, service_state="blocked", errors=_dedupe(errors))
        return ResidentControllerStartDecision(True, daemon_started=False, service_state="authorized_source_only")

    def evaluate_start_once(
        self,
        *,
        config: dict[str, Any],
        broker: BrokerReadinessSnapshot,
        run_authorization_ref: str,
    ) -> ResidentControllerStartDecision:
        start = self.evaluate_start(run_authorization_ref=run_authorization_ref)
        errors = list(start.errors)
        config_result = validate_resident_controller_config(config)
        if not config_result.valid:
            errors.extend(config_result.errors)
        if not broker.connected:
            errors.append("BROKER_NOT_CONNECTED")
        if not broker.subscriptions_ready:
            errors.append("SUBSCRIPTIONS_NOT_READY")
        errors.extend(broker.errors)
        state = "route_ready" if not errors else "blocked"
        evidence = [
            ResidentEvidenceRecord(
                sequence=1,
                record_type="config_validation",
                event_time="source-only",
                payload={
                    "valid": config_result.valid,
                    "config_hash": config_result.config_hash,
                    "live_runtime_allowed": config_result.live_runtime_allowed,
                    "not_business_completion": True,
                },
            ),
            ResidentEvidenceRecord(
                sequence=2,
                record_type="route_readiness",
                event_time="source-only",
                payload={
                    "broker_connected": broker.connected,
                    "subscriptions_ready": broker.subscriptions_ready,
                    "service_state": state,
                    "not_business_completion": True,
                },
            ),
        ]
        return ResidentControllerStartDecision(
            accepted=not errors,
            daemon_started=False,
            service_state=state,
            evidence_records=evidence,
            errors=_dedupe(errors),
        )


def build_status_snapshot(
    *,
    service_state: str,
    broker_connected: bool,
    subscriptions_ready: bool,
    last_heartbeat_at: str,
    pending_assignments: list[str],
    evidence_root: str,
) -> dict[str, Any]:
    return {
        "schema_version": "4.19.resident_controller.status.v1",
        "service_state": service_state,
        "broker_connected": broker_connected,
        "subscriptions_ready": subscriptions_ready,
        "last_heartbeat_at": last_heartbeat_at,
        "pending_assignments": list(pending_assignments),
        "evidence_root": evidence_root,
        "operational_status_only": True,
        "result_candidate_only": True,
        "final_acceptance": False,
        "wbs_pass": False,
        "not_business_completion": True,
    }


def build_drain_offline_record(
    *,
    run_id: str,
    reason_ref: str,
    connected: bool,
    event_time: str,
) -> dict[str, Any]:
    return {
        "schema_version": "4.19.resident_controller.drain_offline.v1",
        "run_id": run_id,
        "reason_ref": reason_ref,
        "event_time": event_time,
        "state": "offline",
        "publish_attempted": bool(connected),
        "broker_mutated": False,
        "config_mutated": False,
        "not_business_completion": True,
    }


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
