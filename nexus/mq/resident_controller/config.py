"""Resident controller config validation and redaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json

from nexus.mq.agent_registry_events import secret_material_errors


RESIDENT_CONTROLLER_CONFIG_SCHEMA_VERSION = "resident_controller.v0.2"
ALLOWED_LAUNCH_MODES = {"disabled", "bounded_uat"}
ALLOWED_COMMANDS = {"controller_init", "bounded_assignment", "duplicate_replay", "drain"}
REQUIRED_NAMESPACE = "nexus.4_19.wbs7_19_14"


@dataclass
class ResidentControllerConfigValidationResult:
    valid: bool
    fail_closed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_hash: str = ""
    redacted_snapshot: dict[str, Any] = field(default_factory=dict)
    live_runtime_allowed: bool = False
    not_business_completion: bool = True


def validate_resident_controller_config(config: dict[str, Any]) -> ResidentControllerConfigValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if config.get("schema_version") != RESIDENT_CONTROLLER_CONFIG_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_RESIDENT_CONTROLLER_CONFIG_SCHEMA")

    controller = _section(config, "controller", errors)
    broker = _section(config, "broker", errors)
    subjects = _section(config, "subjects", errors)
    runtimes = _section(config, "runtimes", errors)
    policy = _section(config, "policy", errors)
    evidence = _section(config, "evidence", errors)
    recovery = _section(config, "recovery", errors)

    _require(controller, "controller_id", "controller.controller_id", errors)
    _require(controller, "runtime_instance_id", "controller.runtime_instance_id", errors)
    _require(controller, "environment", "controller.environment", errors)
    _require(controller, "launch_mode", "controller.launch_mode", errors)
    if not controller.get("run_authorization_ref"):
        errors.append("MISSING_RUN_AUTHORIZATION_REF")
    if not controller.get("allowed_wbs_ids"):
        errors.append("MISSING_ALLOWED_WBS_IDS")
    if controller.get("launch_mode") not in ALLOWED_LAUNCH_MODES:
        errors.append(f"UNSUPPORTED_LAUNCH_MODE: {controller.get('launch_mode')}")

    _require(broker, "nats_url_ref", "broker.nats_url_ref", errors)
    _require(broker, "auth_ref", "broker.auth_ref", errors)
    _require_positive_int(broker, "connect_timeout_seconds", "broker.connect_timeout_seconds", errors)
    _require_positive_int(
        broker,
        "subscription_ready_timeout_seconds",
        "broker.subscription_ready_timeout_seconds",
        errors,
    )

    if subjects.get("namespace") != REQUIRED_NAMESPACE:
        errors.append(f"UNSUPPORTED_SUBJECT_NAMESPACE: {subjects.get('namespace')}")
    if not subjects.get("subscribe_allowlist"):
        errors.append("MISSING_SUBSCRIBE_ALLOWLIST")
    if not subjects.get("publish_allowlist"):
        errors.append("MISSING_PUBLISH_ALLOWLIST")
    for pattern in subjects.get("publish_allowlist", []):
        if ">" in str(pattern):
            errors.append("PUBLISH_ALLOWLIST_CANNOT_CONTAIN_GREATER_WILDCARD")

    if not runtimes.get("allowed_agents"):
        errors.append("MISSING_ALLOWED_AGENTS")
    if not runtimes.get("required_capabilities"):
        errors.append("MISSING_REQUIRED_CAPABILITIES")
    _require_positive_int(runtimes, "heartbeat_ttl_seconds", "runtimes.heartbeat_ttl_seconds", errors)
    _require_positive_int(
        runtimes,
        "stale_after_missed_heartbeats",
        "runtimes.stale_after_missed_heartbeats",
        errors,
    )

    if policy.get("production_business_execution_allowed"):
        errors.append("PRODUCTION_BUSINESS_EXECUTION_NOT_AUTHORIZED")
    if policy.get("private_agent_invocation_allowed"):
        errors.append("PRIVATE_AGENT_INVOCATION_NOT_AUTHORIZED")
    if policy.get("broker_mutation_allowed"):
        errors.append("BROKER_MUTATION_NOT_AUTHORIZED")
    if policy.get("autonomous_acceptance_allowed"):
        errors.append("AUTONOMOUS_ACCEPTANCE_NOT_AUTHORIZED")
    commands = set(policy.get("command_allowlist", []))
    if not commands:
        errors.append("MISSING_COMMAND_ALLOWLIST")
    for command in sorted(commands - ALLOWED_COMMANDS):
        errors.append(f"UNSUPPORTED_COMMAND: {command}")

    _require(evidence, "root", "evidence.root", errors)
    _require(evidence, "raw_log", "evidence.raw_log", errors)
    _require(evidence, "manifest", "evidence.manifest", errors)
    _require(evidence, "summary", "evidence.summary", errors)
    if evidence.get("secret_scan_required") is not True:
        errors.append("SECRET_SCAN_REQUIRED")

    _require(recovery, "checkpoint_file", "recovery.checkpoint_file", errors)
    _require_positive_int(recovery, "reconnect_max_attempts", "recovery.reconnect_max_attempts", errors)
    if not recovery.get("reconnect_backoff_seconds"):
        errors.append("MISSING_RECOVERY_BACKOFF")
    _require_positive_int(
        recovery,
        "assignment_ack_timeout_seconds",
        "recovery.assignment_ack_timeout_seconds",
        errors,
    )
    _require_positive_int(
        recovery,
        "result_candidate_timeout_seconds",
        "recovery.result_candidate_timeout_seconds",
        errors,
    )

    errors.extend(secret_material_errors(config, path="resident_controller_config"))
    snapshot = build_redacted_config_snapshot(config)
    config_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()
    return ResidentControllerConfigValidationResult(
        valid=not errors,
        fail_closed=bool(errors),
        errors=_dedupe(errors),
        warnings=warnings,
        config_hash=f"sha256:{config_hash}",
        redacted_snapshot=snapshot,
        live_runtime_allowed=False,
    )


def build_redacted_config_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    controller = dict(config.get("controller") or {})
    broker = dict(config.get("broker") or {})
    subjects = dict(config.get("subjects") or {})
    runtimes = dict(config.get("runtimes") or {})
    policy = dict(config.get("policy") or {})
    evidence = dict(config.get("evidence") or {})
    recovery = dict(config.get("recovery") or {})
    return {
        "schema_version": config.get("schema_version"),
        "controller": {
            "controller_id": controller.get("controller_id"),
            "runtime_instance_id": controller.get("runtime_instance_id"),
            "environment": controller.get("environment"),
            "launch_mode": controller.get("launch_mode"),
            "run_authorization_ref": controller.get("run_authorization_ref"),
            "allowed_wbs_ids": list(controller.get("allowed_wbs_ids") or []),
        },
        "broker": {
            "nats_url_ref": _redacted_ref(broker.get("nats_url_ref")),
            "auth_ref": _redacted_ref(broker.get("auth_ref")),
            "connect_timeout_seconds": broker.get("connect_timeout_seconds"),
            "subscription_ready_timeout_seconds": broker.get("subscription_ready_timeout_seconds"),
        },
        "subjects": {
            "namespace": subjects.get("namespace"),
            "subscribe_allowlist": list(subjects.get("subscribe_allowlist") or []),
            "publish_allowlist": list(subjects.get("publish_allowlist") or []),
        },
        "runtimes": {
            "allowed_agents": list(runtimes.get("allowed_agents") or []),
            "required_capabilities": list(runtimes.get("required_capabilities") or []),
            "heartbeat_ttl_seconds": runtimes.get("heartbeat_ttl_seconds"),
            "stale_after_missed_heartbeats": runtimes.get("stale_after_missed_heartbeats"),
        },
        "policy": {
            "production_business_execution_allowed": bool(policy.get("production_business_execution_allowed")),
            "private_agent_invocation_allowed": bool(policy.get("private_agent_invocation_allowed")),
            "broker_mutation_allowed": bool(policy.get("broker_mutation_allowed")),
            "autonomous_acceptance_allowed": bool(policy.get("autonomous_acceptance_allowed")),
            "require_non_loopback_for_distributed_uat": bool(policy.get("require_non_loopback_for_distributed_uat")),
            "command_allowlist": list(policy.get("command_allowlist") or []),
        },
        "evidence": {
            "root": evidence.get("root"),
            "raw_log": evidence.get("raw_log"),
            "manifest": evidence.get("manifest"),
            "summary": evidence.get("summary"),
            "secret_scan_required": bool(evidence.get("secret_scan_required")),
        },
        "recovery": {
            "checkpoint_file": recovery.get("checkpoint_file"),
            "reconnect_max_attempts": recovery.get("reconnect_max_attempts"),
            "reconnect_backoff_seconds": list(recovery.get("reconnect_backoff_seconds") or []),
            "assignment_ack_timeout_seconds": recovery.get("assignment_ack_timeout_seconds"),
            "result_candidate_timeout_seconds": recovery.get("result_candidate_timeout_seconds"),
        },
        "redacted_at": datetime.now(timezone.utc).isoformat(),
        "not_business_completion": True,
    }


def _section(config: dict[str, Any], name: str, errors: list[str]) -> dict[str, Any]:
    section = config.get(name)
    if not isinstance(section, dict):
        errors.append(f"MISSING_CONFIG_SECTION: {name}")
        return {}
    return section


def _require(section: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    if not section.get(key):
        errors.append(f"MISSING_REQUIRED_FIELD: {path}")


def _require_positive_int(section: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    value = section.get(key)
    if not isinstance(value, int) or value <= 0:
        errors.append(f"INVALID_POSITIVE_INTEGER: {path}")


def _redacted_ref(value: Any) -> str:
    return "redacted-ref-present" if value else ""


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
