"""Redacted private-agent diagnostic task package builder for WBS 7.12."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.private_agent_contract import PrivateAgentContract, active_contract_errors, task_classification_allows
from nexus.mq.private_context_policy import PrivatePackageInput, evaluate_private_context_policy, redaction_manifest_for


PRIVATE_AGENT_TASK_PACKAGE_SCHEMA_VERSION = "4.19.private_agent_task_package.v1"


@dataclass(frozen=True)
class PrivateTaskPackageRequest:
    task_package_id: str
    assignment_id: str
    contract_id: str
    contract_revision: int
    task_kind: str
    objective: str
    allowed_inputs: list[PrivatePackageInput]
    forbidden_actions: list[str]
    allowed_outputs: list[str]
    evidence_required: list[str]
    timeout_policy_ref: str
    no_go_conditions: list[str]
    ttl_seconds: int = 300
    diagnostic_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateAgentTaskPackage:
    task_package_id: str
    assignment_id: str
    contract_id: str
    contract_revision: int
    task_kind: str
    objective: str
    allowed_inputs: list[dict[str, Any]]
    forbidden_actions: list[str]
    allowed_outputs: list[str]
    evidence_required: list[str]
    timeout_policy_ref: str
    no_go_conditions: list[str]
    redaction_manifest_ref: str
    redaction_manifest: dict[str, Any]
    package_hash: str
    expires_at: str
    schema_version: str = PRIVATE_AGENT_TASK_PACKAGE_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateTaskPackageBuildResult:
    accepted: bool
    package: Optional[PrivateAgentTaskPackage] = None
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def build_private_task_package(
    contract: PrivateAgentContract,
    request: PrivateTaskPackageRequest,
    *,
    now_at: str,
) -> PrivateTaskPackageBuildResult:
    errors = _request_errors(contract, request, now_at=now_at)
    context_result = evaluate_private_context_policy(contract, request.allowed_inputs)
    errors.extend(context_result.errors)
    if errors:
        return PrivateTaskPackageBuildResult(accepted=False, errors=_dedupe(errors))

    expires_at = _expires_at(now_at, request.ttl_seconds)
    manifest = redaction_manifest_for(context_result.allowed_inputs)
    package_without_hash = PrivateAgentTaskPackage(
        task_package_id=request.task_package_id,
        assignment_id=request.assignment_id,
        contract_id=request.contract_id,
        contract_revision=request.contract_revision,
        task_kind=request.task_kind,
        objective=request.objective,
        allowed_inputs=[item.to_dict() for item in context_result.allowed_inputs],
        forbidden_actions=list(request.forbidden_actions),
        allowed_outputs=list(request.allowed_outputs),
        evidence_required=list(request.evidence_required),
        timeout_policy_ref=request.timeout_policy_ref,
        no_go_conditions=list(request.no_go_conditions),
        redaction_manifest_ref=f"redaction-manifest://{request.task_package_id}",
        redaction_manifest=manifest,
        package_hash="",
        expires_at=expires_at,
    )
    package_hash = _package_hash(package_without_hash)
    package = replace(package_without_hash, package_hash=package_hash)
    validation_errors = validate_private_task_package(package, contract=contract, now_at=now_at)
    if validation_errors:
        return PrivateTaskPackageBuildResult(accepted=False, errors=validation_errors)
    return PrivateTaskPackageBuildResult(accepted=True, package=package)


def validate_private_task_package(
    package: PrivateAgentTaskPackage,
    *,
    contract: Optional[PrivateAgentContract] = None,
    now_at: Optional[str] = None,
) -> list[str]:
    errors: list[str] = []
    if package.schema_version != PRIVATE_AGENT_TASK_PACKAGE_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_PRIVATE_TASK_PACKAGE_SCHEMA")
    if package.not_business_completion is not True:
        errors.append("PRIVATE_TASK_PACKAGE_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in [
        "task_package_id",
        "assignment_id",
        "contract_id",
        "task_kind",
        "objective",
        "timeout_policy_ref",
        "redaction_manifest_ref",
        "package_hash",
        "expires_at",
    ]:
        if not getattr(package, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if package.contract_revision <= 0:
        errors.append("PRIVATE_TASK_PACKAGE_CONTRACT_REVISION_INVALID")
    if not package.allowed_inputs:
        errors.append("PRIVATE_TASK_PACKAGE_INPUTS_REQUIRED")
    if not package.evidence_required:
        errors.append("PRIVATE_TASK_PACKAGE_EVIDENCE_REQUIRED")
    if not package.no_go_conditions:
        errors.append("PRIVATE_TASK_PACKAGE_NO_GO_CONDITIONS_REQUIRED")
    if package.task_kind != "diagnostic":
        errors.append("PRIVATE_DIAGNOSTIC_ONLY")
    expires_dt = _parse_iso(package.expires_at)
    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    if expires_dt is None:
        errors.append("PRIVATE_TASK_PACKAGE_EXPIRES_AT_INVALID")
    elif now_dt is None or expires_dt <= now_dt:
        errors.append("PRIVATE_TASK_PACKAGE_EXPIRED")
    if package.package_hash and package.package_hash != _package_hash(replace(package, package_hash="")):
        errors.append("PRIVATE_TASK_PACKAGE_HASH_MISMATCH")
    if contract is not None:
        if package.contract_id != contract.contract_id or package.contract_revision != contract.contract_revision:
            errors.append("PRIVATE_TASK_PACKAGE_CONTRACT_MISMATCH")
        if not task_classification_allows(contract.max_task_package_classification, package.task_kind):
            errors.append("PRIVATE_TASK_CLASSIFICATION_NOT_ALLOWED")
    errors.extend(secret_material_errors(package.to_dict(), path="private_task_package"))
    return _dedupe(errors)


def _request_errors(contract: PrivateAgentContract, request: PrivateTaskPackageRequest, *, now_at: str) -> list[str]:
    errors = active_contract_errors(contract, now_at=now_at)
    if request.not_business_completion is not True:
        errors.append("PRIVATE_TASK_PACKAGE_REQUEST_CANNOT_BE_BUSINESS_COMPLETION")
    if request.diagnostic_only and request.task_kind != "diagnostic":
        errors.append("PRIVATE_DIAGNOSTIC_ONLY")
    if request.contract_id != contract.contract_id or request.contract_revision != contract.contract_revision:
        errors.append("PRIVATE_TASK_PACKAGE_CONTRACT_MISMATCH")
    if request.ttl_seconds <= 0:
        errors.append("PRIVATE_TASK_PACKAGE_TTL_INVALID")
    for field_name in [
        "task_package_id",
        "assignment_id",
        "contract_id",
        "task_kind",
        "objective",
        "timeout_policy_ref",
    ]:
        if not getattr(request, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if not request.evidence_required:
        errors.append("PRIVATE_TASK_PACKAGE_EVIDENCE_REQUIRED")
    if not request.no_go_conditions:
        errors.append("PRIVATE_TASK_PACKAGE_NO_GO_CONDITIONS_REQUIRED")
    errors.extend(secret_material_errors(request.to_dict(), path="private_task_package_request"))
    return _dedupe(errors)


def _package_hash(package: PrivateAgentTaskPackage) -> str:
    payload = package.to_dict()
    payload["package_hash"] = ""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def _expires_at(now_at: str, ttl_seconds: int) -> str:
    now_dt = _parse_iso(now_at) or datetime.now(timezone.utc)
    return (now_dt + timedelta(seconds=ttl_seconds)).isoformat()


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
