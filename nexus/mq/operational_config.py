"""Phase 6 operational configuration validation.

This module validates local/deployment manifests without mutating any live
broker, host, credential, or notification infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import hashlib
import json


UTC = timezone.utc
APPROVED_LOCAL_BROKER_PREFIXES = ("nats://127.0.0.1:", "nats://localhost:")
APPROVED_STAGING_BROKER_PREFIXES = ("nats://192.168.", "nats://10.", "nats://172.")
KNOWN_PRODUCTION_FLAGS = {
    "broker_hardening",
    "observability",
    "alert_events",
    "deployment_validation",
    "controlled_resilience",
}


@dataclass
class StreamPolicy:
    name: str
    subjects: list[str]
    retention: str
    storage: str
    max_age_seconds: int
    max_bytes: int
    max_messages: int
    replicas: int = 1
    replay_window_seconds: int = 0


@dataclass
class ConsumerPolicy:
    durable_name: str
    filter_subject: str
    ack_policy: str
    ack_wait_seconds: int
    max_deliver: int
    replay_policy: str
    pending_limit: int
    inactive_threshold_seconds: int


@dataclass
class BrokerConfig:
    broker_urls: list[str]
    stream_policies: list[StreamPolicy]
    consumer_policies: list[ConsumerPolicy]
    subject_allowlist: list[str]
    dlq_subject: str
    health_threshold_seconds: int


@dataclass
class StoreConfig:
    dsn: str
    schema_version: str
    required_families: list[str]
    read_write_required: bool = True


@dataclass
class AlertingConfig:
    event_store: str
    severity_policy_ref: str
    routing_policy_ref: str
    unresolved_threshold_seconds: int
    real_delivery_enabled: bool = False


@dataclass
class RuntimeProcessConfig:
    runtime_instance_id: str
    agent_id: str
    role: str
    capabilities: list[str]
    process_supervisor: str
    restart_policy: str


@dataclass
class OperationalManifest:
    manifest_version: str
    environment: str
    broker: BrokerConfig
    durable_state: StoreConfig
    evidence: StoreConfig
    alerting: AlertingConfig
    runtime_process: RuntimeProcessConfig
    feature_flags: dict[str, bool] = field(default_factory=dict)
    secret_refs: dict[str, str] = field(default_factory=dict)
    diagnostic_read_only: bool = False
    rollout_phase: str = "dry_run"
    approved_config_ref: Optional[str] = None

    @property
    def config_hash(self) -> str:
        payload = json.dumps(redact_manifest(self), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class OperationalValidationResult:
    valid: bool
    fail_closed: bool
    diagnostic_read_only: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest_version: Optional[str] = None
    config_hash: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def validate_operational_manifest(manifest: OperationalManifest) -> OperationalValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not manifest.manifest_version:
        errors.append("MISSING_REQUIRED_FIELD: manifest_version")
    if manifest.environment not in {"local", "staging", "production"}:
        errors.append(f"INVALID_ENVIRONMENT: {manifest.environment}")

    _validate_broker(manifest, errors, warnings)
    _validate_store("durable_state", manifest.durable_state, errors)
    _validate_store("evidence", manifest.evidence, errors)
    _validate_alerting(manifest.alerting, errors)
    _validate_runtime_process(manifest.runtime_process, errors)
    _validate_feature_flags(manifest, errors)
    _validate_secret_refs(manifest.secret_refs, errors)

    fail_closed = bool(errors)
    return OperationalValidationResult(
        valid=not errors,
        fail_closed=fail_closed,
        diagnostic_read_only=manifest.diagnostic_read_only and fail_closed,
        errors=errors,
        warnings=warnings,
        manifest_version=manifest.manifest_version,
        config_hash=manifest.config_hash,
    )


def validate_reload(current: OperationalManifest, candidate: OperationalManifest) -> dict[str, Any]:
    result = validate_operational_manifest(candidate)
    return {
        "accepted": result.valid,
        "kept_prior_config": not result.valid,
        "prior_config_hash": current.config_hash,
        "candidate_config_hash": candidate.config_hash,
        "errors": list(result.errors),
        "not_business_completion": True,
    }


def redact_manifest(manifest: OperationalManifest) -> dict[str, Any]:
    return {
        "manifest_version": manifest.manifest_version,
        "environment": manifest.environment,
        "broker": {
            "broker_urls": [_redact_url(url) for url in manifest.broker.broker_urls],
            "streams": [policy.name for policy in manifest.broker.stream_policies],
            "consumers": [policy.durable_name for policy in manifest.broker.consumer_policies],
            "subject_allowlist": list(manifest.broker.subject_allowlist),
            "dlq_subject": manifest.broker.dlq_subject,
        },
        "durable_state": {
            "dsn": _redact_dsn(manifest.durable_state.dsn),
            "schema_version": manifest.durable_state.schema_version,
            "required_families": list(manifest.durable_state.required_families),
        },
        "evidence": {
            "dsn": _redact_dsn(manifest.evidence.dsn),
            "schema_version": manifest.evidence.schema_version,
            "required_families": list(manifest.evidence.required_families),
        },
        "alerting": {
            "event_store": _redact_dsn(manifest.alerting.event_store),
            "severity_policy_ref": manifest.alerting.severity_policy_ref,
            "routing_policy_ref": manifest.alerting.routing_policy_ref,
            "real_delivery_enabled": manifest.alerting.real_delivery_enabled,
        },
        "runtime_process": {
            "runtime_instance_id": manifest.runtime_process.runtime_instance_id,
            "agent_id": manifest.runtime_process.agent_id,
            "role": manifest.runtime_process.role,
            "capabilities": list(manifest.runtime_process.capabilities),
        },
        "feature_flags": dict(manifest.feature_flags),
        "secret_refs": {name: "ref-present" if value else "" for name, value in manifest.secret_refs.items()},
        "diagnostic_read_only": manifest.diagnostic_read_only,
        "rollout_phase": manifest.rollout_phase,
        "approved_config_ref": manifest.approved_config_ref,
    }


def _validate_broker(manifest: OperationalManifest, errors: list[str], warnings: list[str]) -> None:
    broker = manifest.broker
    if not broker.broker_urls:
        errors.append("MISSING_REQUIRED_FIELD: broker.broker_urls")
    for url in broker.broker_urls:
        if _has_secret_material(url):
            errors.append("SECRET_LEAK: broker_url")
        if manifest.environment == "production":
            errors.append("PRODUCTION_BROKER_TOPOLOGY_DEFERRED")
        elif manifest.environment == "local" and not url.startswith(APPROVED_LOCAL_BROKER_PREFIXES):
            warnings.append(f"LOCAL_BROKER_ENDPOINT_NOT_LOOPBACK: {_redact_url(url)}")
        elif manifest.environment == "staging" and not url.startswith(APPROVED_STAGING_BROKER_PREFIXES):
            warnings.append(f"STAGING_BROKER_ENDPOINT_NOT_PRIVATE: {_redact_url(url)}")
    if not broker.stream_policies:
        errors.append("MISSING_REQUIRED_FIELD: broker.stream_policies")
    if not broker.consumer_policies:
        errors.append("MISSING_REQUIRED_FIELD: broker.consumer_policies")
    if not broker.subject_allowlist:
        errors.append("MISSING_REQUIRED_FIELD: broker.subject_allowlist")
    if not broker.dlq_subject:
        errors.append("MISSING_REQUIRED_FIELD: broker.dlq_subject")
    for policy in broker.stream_policies:
        if not policy.subjects:
            errors.append(f"STREAM_POLICY_MISSING_SUBJECTS: {policy.name}")
        if policy.max_bytes <= 0 or policy.max_messages <= 0 or policy.max_age_seconds <= 0:
            errors.append(f"STREAM_POLICY_UNBOUNDED_CAPACITY: {policy.name}")
    for policy in broker.consumer_policies:
        if policy.ack_policy not in {"explicit", "manual"}:
            errors.append(f"CONSUMER_POLICY_INVALID_ACK_POLICY: {policy.durable_name}")
        if policy.ack_wait_seconds <= 0 or policy.max_deliver <= 0 or policy.pending_limit <= 0:
            errors.append(f"CONSUMER_POLICY_UNBOUNDED: {policy.durable_name}")


def _validate_store(section: str, config: StoreConfig, errors: list[str]) -> None:
    if not config.dsn:
        errors.append(f"MISSING_REQUIRED_FIELD: {section}.dsn")
    if _has_secret_material(config.dsn):
        errors.append(f"SECRET_LEAK: {section}.dsn")
    if not config.schema_version:
        errors.append(f"MISSING_REQUIRED_FIELD: {section}.schema_version")
    if not config.required_families:
        errors.append(f"MISSING_REQUIRED_FIELD: {section}.required_families")


def _validate_alerting(config: AlertingConfig, errors: list[str]) -> None:
    if not config.event_store:
        errors.append("MISSING_REQUIRED_FIELD: alerting.event_store")
    if not config.severity_policy_ref:
        errors.append("MISSING_REQUIRED_FIELD: alerting.severity_policy_ref")
    if not config.routing_policy_ref:
        errors.append("MISSING_REQUIRED_FIELD: alerting.routing_policy_ref")
    if config.real_delivery_enabled:
        errors.append("REAL_NOTIFICATION_DELIVERY_OUT_OF_SCOPE")


def _validate_runtime_process(config: RuntimeProcessConfig, errors: list[str]) -> None:
    if not config.runtime_instance_id:
        errors.append("MISSING_REQUIRED_FIELD: runtime_process.runtime_instance_id")
    if not config.agent_id:
        errors.append("MISSING_REQUIRED_FIELD: runtime_process.agent_id")
    if not config.role:
        errors.append("MISSING_REQUIRED_FIELD: runtime_process.role")
    if not config.capabilities:
        errors.append("MISSING_REQUIRED_FIELD: runtime_process.capabilities")


def _validate_feature_flags(manifest: OperationalManifest, errors: list[str]) -> None:
    if manifest.environment == "production":
        unknown = set(manifest.feature_flags) - KNOWN_PRODUCTION_FLAGS
        for flag in sorted(unknown):
            errors.append(f"UNKNOWN_PRODUCTION_FEATURE_FLAG: {flag}")


def _validate_secret_refs(secret_refs: dict[str, str], errors: list[str]) -> None:
    for key, value in secret_refs.items():
        if not value:
            errors.append(f"MISSING_SECRET_REF: {key}")
        if _has_secret_material(value):
            errors.append(f"SECRET_LEAK: secret_refs.{key}")


def _redact_url(value: str) -> str:
    if "@" not in value:
        return value
    scheme, rest = value.split("://", 1) if "://" in value else ("", value)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}" if scheme else f"***@{host}"


def _redact_dsn(value: str) -> str:
    return _redact_url(value)


def _has_secret_material(value: str) -> bool:
    lowered = value.lower()
    return _has_embedded_url_credentials(value) or any(
        marker in lowered for marker in ("password=", "token=", "secret=", "bearer ")
    )


def _has_embedded_url_credentials(value: str) -> bool:
    if "://" not in value or "@" not in value:
        return False
    rest = value.split("://", 1)[1]
    userinfo = rest.split("@", 1)[0]
    return ":" in userinfo or bool(userinfo)
