"""Private-agent diagnostic eligibility gate for WBS 7.12."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.private_agent_contract import PrivateAgentContract, active_contract_errors, task_classification_allows
from nexus.mq.private_contract_registry import PrivateContractRegistryStore


class PrivateAgentRejectionCode:
    PRIVATE_CONTRACT_MISSING = "PRIVATE_CONTRACT_MISSING"
    PRIVATE_CONTRACT_NOT_ACCEPTED = "PRIVATE_CONTRACT_NOT_ACCEPTED"
    PRIVATE_CONTRACT_NOT_ACTIVE = "PRIVATE_CONTRACT_NOT_ACTIVE"
    PRIVATE_CONTRACT_EXPIRED = "PRIVATE_CONTRACT_EXPIRED"
    PRIVATE_CONTRACT_MALFORMED = "PRIVATE_CONTRACT_MALFORMED"
    PRIVATE_CONTRACT_TRUTH_UNVERIFIED = "PRIVATE_CONTRACT_TRUTH_UNVERIFIED"
    PRIVATE_CONTRACT_STORE_UNAVAILABLE = "PRIVATE_CONTRACT_STORE_UNAVAILABLE"
    PRIVATE_CONTRACT_BLOCKING_ANOMALY_PRESENT = "PRIVATE_CONTRACT_BLOCKING_ANOMALY_PRESENT"
    PRIVATE_ADAPTER_RECORD_MISSING = "PRIVATE_ADAPTER_RECORD_MISSING"
    PRIVATE_ADAPTER_STALE = "PRIVATE_ADAPTER_STALE"
    PRIVATE_ADAPTER_OFFLINE = "PRIVATE_ADAPTER_OFFLINE"
    PRIVATE_ADAPTER_NOT_READY = "PRIVATE_ADAPTER_NOT_READY"
    PRIVATE_ADAPTER_IDENTITY_MISMATCH = "PRIVATE_ADAPTER_IDENTITY_MISMATCH"
    PRIVATE_ADAPTER_TRUTH_UNVERIFIED = "PRIVATE_ADAPTER_TRUTH_UNVERIFIED"
    PRIVATE_ADAPTER_MALFORMED = "PRIVATE_ADAPTER_MALFORMED"
    PRIVATE_ADAPTER_NOT_ACCEPTING_WORK = "PRIVATE_ADAPTER_NOT_ACCEPTING_WORK"
    PRIVATE_CAPABILITY_MISMATCH = "PRIVATE_CAPABILITY_MISMATCH"
    PRIVATE_AUTHORITY_SCOPE_MISMATCH = "PRIVATE_AUTHORITY_SCOPE_MISMATCH"
    PRIVATE_PRIVACY_SCOPE_MISMATCH = "PRIVATE_PRIVACY_SCOPE_MISMATCH"
    PRIVATE_TASK_CLASSIFICATION_NOT_ALLOWED = "PRIVATE_TASK_CLASSIFICATION_NOT_ALLOWED"
    PRIVATE_DIAGNOSTIC_ONLY = "PRIVATE_DIAGNOSTIC_ONLY"
    PRIVATE_NO_ELIGIBLE_CONTRACT = "PRIVATE_NO_ELIGIBLE_CONTRACT"


@dataclass(frozen=True)
class PrivateAgentEligibilityRequest:
    request_id: str
    correlation_id: str
    contract_id: str
    invocation_id: str
    required_capability: str
    required_authority_scope: str
    required_privacy_scope: str
    task_kind: str = "diagnostic"
    diagnostic_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateAgentEligibilityDecision:
    accepted: bool
    contract_id: Optional[str] = None
    adapter_agent_id: Optional[str] = None
    adapter_runtime_instance_id: Optional[str] = None
    registry_revision_seen: Optional[int] = None
    heartbeat_timestamp_observed: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    read_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_private_agent_from_registry_service(
    request: PrivateAgentEligibilityRequest,
    contract_registry: PrivateContractRegistryStore,
    registry_service: AgentRegistryService,
    *,
    now_at: str,
) -> PrivateAgentEligibilityDecision:
    contract_read = contract_registry.get_contract(request.contract_id, now_at=now_at)
    if not contract_read.accepted or contract_read.contract is None:
        return _blocked(_normalize_contract_errors(contract_read.errors), contract_id=request.contract_id)
    adapter_read = registry_service.read_registry_record(contract_read.contract.adapter_agent_id, now_at=now_at)
    if not adapter_read.accepted or adapter_read.record is None:
        return _blocked(
            _normalize_adapter_errors(adapter_read.errors),
            contract_id=request.contract_id,
            adapter_agent_id=contract_read.contract.adapter_agent_id,
        )
    return evaluate_private_agent_eligibility(
        request,
        contract_read.contract,
        adapter_read.record,
        registry_revision_seen=adapter_read.revision,
        now_at=now_at,
    )


def evaluate_private_agent_eligibility(
    request: PrivateAgentEligibilityRequest,
    contract: PrivateAgentContract,
    adapter_record: Optional[AgentRegistryRecord],
    *,
    registry_revision_seen: Optional[int],
    now_at: str,
) -> PrivateAgentEligibilityDecision:
    errors: list[str] = []
    if request.not_business_completion is not True:
        errors.append("PRIVATE_REQUEST_CANNOT_BE_BUSINESS_COMPLETION")
    if request.diagnostic_only and request.task_kind != "diagnostic":
        errors.append(PrivateAgentRejectionCode.PRIVATE_DIAGNOSTIC_ONLY)
    errors.extend(_request_required_field_errors(request))
    errors.extend(_normalize_contract_errors(active_contract_errors(contract, now_at=now_at)))

    if request.invocation_id not in {item.invocation_id for item in contract.allowed_invocations}:
        errors.append("PRIVATE_INVOCATION_NOT_ALLOWLISTED")
    if request.required_capability not in contract.capability_claims:
        errors.append(PrivateAgentRejectionCode.PRIVATE_CAPABILITY_MISMATCH)
    if request.required_authority_scope not in contract.authority_scope:
        errors.append(PrivateAgentRejectionCode.PRIVATE_AUTHORITY_SCOPE_MISMATCH)
    if request.required_privacy_scope not in contract.privacy_scope:
        errors.append(PrivateAgentRejectionCode.PRIVATE_PRIVACY_SCOPE_MISMATCH)
    if not task_classification_allows(contract.max_task_package_classification, request.task_kind):
        errors.append(PrivateAgentRejectionCode.PRIVATE_TASK_CLASSIFICATION_NOT_ALLOWED)

    adapter_errors = _adapter_errors(contract, adapter_record, now_at=now_at)
    errors.extend(adapter_errors)

    if errors:
        return _blocked(
            errors,
            contract_id=contract.contract_id,
            adapter_agent_id=contract.adapter_agent_id,
            adapter_runtime_instance_id=contract.adapter_runtime_instance_id,
            registry_revision_seen=registry_revision_seen,
            heartbeat_timestamp_observed=adapter_record.last_heartbeat_at if adapter_record else None,
        )
    return PrivateAgentEligibilityDecision(
        accepted=True,
        contract_id=contract.contract_id,
        adapter_agent_id=contract.adapter_agent_id,
        adapter_runtime_instance_id=contract.adapter_runtime_instance_id,
        registry_revision_seen=registry_revision_seen,
        heartbeat_timestamp_observed=adapter_record.last_heartbeat_at if adapter_record else None,
    )


def _adapter_errors(
    contract: PrivateAgentContract,
    adapter_record: Optional[AgentRegistryRecord],
    *,
    now_at: str,
) -> list[str]:
    if adapter_record is None:
        return [PrivateAgentRejectionCode.PRIVATE_ADAPTER_RECORD_MISSING]
    errors: list[str] = []
    if adapter_record.agent_id != contract.adapter_agent_id:
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_IDENTITY_MISMATCH)
    if adapter_record.runtime_instance_id != contract.adapter_runtime_instance_id:
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_IDENTITY_MISMATCH)
    if adapter_record.registry_status != "active" or adapter_record.initialization_status != "ready":
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_NOT_READY)
    if adapter_record.presence_state in {"offline", "stale"}:
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_OFFLINE)
    elif adapter_record.presence_state != "idle":
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_NOT_READY)
    if not adapter_record.accepting_new_work:
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_NOT_ACCEPTING_WORK)
    if not adapter_record.last_heartbeat_at:
        errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_STALE)
    else:
        heartbeat_dt = _parse_iso(adapter_record.last_heartbeat_at)
        now_dt = _parse_iso(now_at)
        if heartbeat_dt is None or now_dt is None or adapter_record.heartbeat_ttl_seconds <= 0:
            errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_MALFORMED)
        elif (now_dt - heartbeat_dt).total_seconds() > adapter_record.heartbeat_ttl_seconds:
            errors.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_STALE)
    return _dedupe(errors)


def _normalize_contract_errors(errors: list[str]) -> list[str]:
    normalized: list[str] = []
    for error in errors:
        if error == "PRIVATE_CONTRACT_MISSING":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_MISSING)
        elif error == "PRIVATE_CONTRACT_TRUTH_UNVERIFIED":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_TRUTH_UNVERIFIED)
        elif error == "PRIVATE_CONTRACT_STORE_CORRUPTED":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_STORE_UNAVAILABLE)
        elif error == "PRIVATE_CONTRACT_EXPIRED":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_EXPIRED)
        elif error == "PRIVATE_CONTRACT_BLOCKING_ANOMALY_PRESENT":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_BLOCKING_ANOMALY_PRESENT)
        elif error == "PRIVATE_CONTRACT_NOT_ACCEPTED" or error.startswith("PRIVATE_CONTRACT_ACTIVE_REQUIRES"):
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_NOT_ACCEPTED)
        elif error.startswith("PRIVATE_CONTRACT_NOT_ACTIVE"):
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_NOT_ACTIVE)
        elif error.startswith("MALFORMED_PRIVATE_CONTRACT_ROW") or error.startswith("UNSUPPORTED_PRIVATE_CONTRACT"):
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_MALFORMED)
        elif error.startswith("SECRET_MATERIAL"):
            normalized.append(PrivateAgentRejectionCode.PRIVATE_CONTRACT_MALFORMED)
        else:
            normalized.append(error)
    return _dedupe(normalized)


def _normalize_adapter_errors(errors: list[str]) -> list[str]:
    normalized: list[str] = []
    for error in errors:
        if error == "REGISTRY_RECORD_NOT_FOUND":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_RECORD_MISSING)
        elif error == "REGISTRY_TRUTH_UNVERIFIED":
            normalized.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_TRUTH_UNVERIFIED)
        elif error == "REGISTRY_STORE_CORRUPTED" or error.startswith("MALFORMED_REGISTRY_ROW"):
            normalized.append(PrivateAgentRejectionCode.PRIVATE_ADAPTER_MALFORMED)
        else:
            normalized.append(error)
    return _dedupe(normalized)


def _request_required_field_errors(request: PrivateAgentEligibilityRequest) -> list[str]:
    errors: list[str] = []
    for field_name in [
        "request_id",
        "correlation_id",
        "contract_id",
        "invocation_id",
        "required_capability",
        "required_authority_scope",
        "required_privacy_scope",
        "task_kind",
    ]:
        if not getattr(request, field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    return errors


def _blocked(
    errors: list[str],
    *,
    contract_id: Optional[str] = None,
    adapter_agent_id: Optional[str] = None,
    adapter_runtime_instance_id: Optional[str] = None,
    registry_revision_seen: Optional[int] = None,
    heartbeat_timestamp_observed: Optional[str] = None,
) -> PrivateAgentEligibilityDecision:
    return PrivateAgentEligibilityDecision(
        accepted=False,
        contract_id=contract_id,
        adapter_agent_id=adapter_agent_id,
        adapter_runtime_instance_id=adapter_runtime_instance_id,
        registry_revision_seen=registry_revision_seen,
        heartbeat_timestamp_observed=heartbeat_timestamp_observed,
        errors=_dedupe(errors) or [PrivateAgentRejectionCode.PRIVATE_NO_ELIGIBLE_CONTRACT],
    )


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
