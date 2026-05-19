"""Private / contract-only agent contract model for WBS 7.12.

Contracts describe a black-box private agent boundary. They do not create
trusted runtime registry records, grant business authority, or imply readiness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors


PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION = "4.19.private_agent_contract.v1"
TRUST_CLASSES = {"private_local", "external_api", "contractor_cli", "managed_daemon"}
CONTRACT_STATUSES = {"draft", "reviewed", "active", "suspended", "revoked", "expired"}
INVOCATION_TYPES = {"cli", "http_api"}
TASK_PACKAGE_CLASSIFICATIONS = {
    "diagnostic": 0,
    "non_business_probe": 1,
    "bounded_business_candidate": 2,
}
DEFAULT_FORBIDDEN_CONTEXT = {
    "live_credentials",
    "long_term_memory",
    "full_repo_checkout",
    "unrelated_shared_docs",
    "private_chat_history",
    "operator_private_files",
    "business_authority_state",
    "raw_evidence_bodies",
    "external_network_credentials",
    "cross_project_context",
}


@dataclass(frozen=True)
class AllowedPrivateInvocation:
    invocation_id: str
    invocation_type: str
    command_or_endpoint_ref: str
    allowed_args_schema_ref: str
    timeout_policy_ref: str
    retry_policy_ref: str
    allowed_args: dict[str, list[str]] = field(default_factory=dict)
    allowed_env_refs: list[str] = field(default_factory=list)
    forbidden_env_keys: list[str] = field(default_factory=list)
    idempotency_policy_ref: str = "idempotency://private-agent/same-package-hash"
    artifact_capture_policy_ref: str = "artifact-capture://private-agent/diagnostic"
    max_output_bytes: int = 8192
    network_policy_ref: str = "network://private-agent/no-expansion"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateAgentContract:
    contract_id: str
    contract_revision: int
    agent_display_name: str
    owner: str
    trust_class: str
    adapter_host_ref: str
    adapter_agent_id: str
    adapter_runtime_instance_id: str
    contract_status: str
    allowed_invocations: list[AllowedPrivateInvocation]
    capability_claims: list[str]
    authority_scope: list[str]
    privacy_scope: list[str]
    forbidden_context: list[str]
    input_schema_ref: str
    output_schema_ref: str
    evidence_requirements: list[str]
    validation_policy_ref: str
    max_task_package_classification: str
    business_completion_authority: bool
    diagnostic_only_until: str
    accepted_by: str
    accepted_at: str
    expires_at: str
    last_review_evidence_ref: str
    blocking_anomaly_refs: list[str] = field(default_factory=list)
    schema_version: str = PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateContractValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_private_agent_contract(
    contract: PrivateAgentContract,
    *,
    now_at: Optional[str] = None,
) -> PrivateContractValidationResult:
    errors: list[str] = []
    if contract.schema_version != PRIVATE_AGENT_CONTRACT_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_PRIVATE_CONTRACT_SCHEMA")
    if contract.not_business_completion is not True:
        errors.append("PRIVATE_CONTRACT_CANNOT_BE_BUSINESS_COMPLETION")
    if contract.business_completion_authority:
        errors.append("PRIVATE_CONTRACT_CANNOT_GRANT_BUSINESS_COMPLETION_AUTHORITY")
    if contract.contract_revision <= 0:
        errors.append("PRIVATE_CONTRACT_REVISION_INVALID")
    if contract.trust_class not in TRUST_CLASSES:
        errors.append(f"PRIVATE_CONTRACT_TRUST_CLASS_INVALID: {contract.trust_class}")
    if contract.contract_status not in CONTRACT_STATUSES:
        errors.append(f"PRIVATE_CONTRACT_STATUS_INVALID: {contract.contract_status}")
    if contract.max_task_package_classification not in TASK_PACKAGE_CLASSIFICATIONS:
        errors.append(f"PRIVATE_TASK_CLASSIFICATION_INVALID: {contract.max_task_package_classification}")

    for field_name in [
        "contract_id",
        "agent_display_name",
        "owner",
        "adapter_host_ref",
        "adapter_agent_id",
        "adapter_runtime_instance_id",
        "input_schema_ref",
        "output_schema_ref",
        "validation_policy_ref",
        "diagnostic_only_until",
        "expires_at",
        "last_review_evidence_ref",
    ]:
        if not getattr(contract, field_name):
            errors.append(f"MISSING_{field_name.upper()}")

    if not contract.allowed_invocations:
        errors.append("PRIVATE_CONTRACT_INVOCATION_ALLOWLIST_REQUIRED")
    if not contract.capability_claims:
        errors.append("PRIVATE_CONTRACT_CAPABILITY_CLAIMS_REQUIRED")
    if not contract.authority_scope:
        errors.append("PRIVATE_CONTRACT_AUTHORITY_SCOPE_REQUIRED")
    if not contract.privacy_scope:
        errors.append("PRIVATE_CONTRACT_PRIVACY_SCOPE_REQUIRED")
    if not contract.evidence_requirements:
        errors.append("PRIVATE_CONTRACT_EVIDENCE_REQUIREMENTS_REQUIRED")

    for invocation in contract.allowed_invocations:
        errors.extend(_validate_invocation(invocation))

    if contract.contract_status == "active":
        for field_name in ["accepted_by", "accepted_at", "last_review_evidence_ref"]:
            if not getattr(contract, field_name):
                errors.append(f"PRIVATE_CONTRACT_ACTIVE_REQUIRES_{field_name.upper()}")

    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    accepted_dt = _parse_iso(contract.accepted_at)
    expires_dt = _parse_iso(contract.expires_at)
    diagnostic_until_dt = _parse_iso(contract.diagnostic_only_until)
    if contract.accepted_at and accepted_dt is None:
        errors.append("PRIVATE_CONTRACT_ACCEPTED_AT_INVALID")
    if expires_dt is None:
        errors.append("PRIVATE_CONTRACT_EXPIRES_AT_INVALID")
    elif now_dt is None or expires_dt <= now_dt:
        errors.append("PRIVATE_CONTRACT_EXPIRED")
    if diagnostic_until_dt is None:
        errors.append("PRIVATE_CONTRACT_DIAGNOSTIC_ONLY_UNTIL_INVALID")

    errors.extend(secret_material_errors(contract.to_dict(), path="private_contract"))
    return PrivateContractValidationResult(valid=not errors, errors=_dedupe(errors))


def task_classification_allows(max_classification: str, requested_classification: str) -> bool:
    if max_classification not in TASK_PACKAGE_CLASSIFICATIONS:
        return False
    if requested_classification not in TASK_PACKAGE_CLASSIFICATIONS:
        return False
    return TASK_PACKAGE_CLASSIFICATIONS[requested_classification] <= TASK_PACKAGE_CLASSIFICATIONS[max_classification]


def active_contract_errors(contract: PrivateAgentContract, *, now_at: str) -> list[str]:
    validation = validate_private_agent_contract(contract, now_at=now_at)
    errors = list(validation.errors)
    if contract.contract_status != "active":
        if contract.contract_status in {"suspended", "revoked", "expired"}:
            errors.append(f"PRIVATE_CONTRACT_NOT_ACTIVE: {contract.contract_status}")
        else:
            errors.append("PRIVATE_CONTRACT_NOT_ACCEPTED")
    if contract.blocking_anomaly_refs:
        errors.append("PRIVATE_CONTRACT_BLOCKING_ANOMALY_PRESENT")
    return _dedupe(errors)


def _validate_invocation(invocation: AllowedPrivateInvocation) -> list[str]:
    errors: list[str] = []
    if not invocation.invocation_id:
        errors.append("PRIVATE_INVOCATION_ID_REQUIRED")
    if invocation.invocation_type not in INVOCATION_TYPES:
        errors.append(f"PRIVATE_INVOCATION_TYPE_INVALID: {invocation.invocation_type}")
    for field_name in [
        "command_or_endpoint_ref",
        "allowed_args_schema_ref",
        "timeout_policy_ref",
        "retry_policy_ref",
        "idempotency_policy_ref",
        "artifact_capture_policy_ref",
        "network_policy_ref",
    ]:
        if not getattr(invocation, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if invocation.max_output_bytes <= 0:
        errors.append("PRIVATE_INVOCATION_MAX_OUTPUT_BYTES_INVALID")
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
