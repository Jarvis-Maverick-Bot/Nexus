"""Read-only redacted private-agent projection helpers for Agent Access."""

from __future__ import annotations

from typing import Any, Optional

from nexus.mq.operational_observability import redact_payload
from nexus.mq.private_agent_contract import PrivateAgentContract
from nexus.mq.private_agent_eligibility import PrivateAgentEligibilityDecision
from nexus.mq.private_invocation_runner import PrivateDiagnosticRunResult
from nexus.mq.private_result_validators import PrivateValidationDecision


PRIVATE_AGENT_PROJECTION_FIELDS = {
    "projection_type",
    "contract_id",
    "contract_revision",
    "contract_status",
    "trust_class",
    "adapter_agent_id",
    "adapter_runtime_instance_id",
    "diagnostic_only",
    "eligibility_status",
    "invocation_status",
    "task_package_id",
    "task_package_hash",
    "result_id",
    "result_state",
    "evidence_status",
    "safety_status",
    "governed_status",
    "business_state_committed",
    "rejection_codes",
    "evidence_refs",
    "read_only",
    "not_business_completion",
}


def build_private_agent_projection(
    *,
    contract: PrivateAgentContract,
    eligibility: Optional[PrivateAgentEligibilityDecision] = None,
    diagnostic_run: Optional[PrivateDiagnosticRunResult] = None,
    validation: Optional[PrivateValidationDecision] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "projection_type": "private_agent_contract",
        "contract_id": contract.contract_id,
        "contract_revision": contract.contract_revision,
        "contract_status": contract.contract_status,
        "trust_class": contract.trust_class,
        "adapter_agent_id": contract.adapter_agent_id,
        "adapter_runtime_instance_id": contract.adapter_runtime_instance_id,
        "diagnostic_only": True,
        "eligibility_status": _eligibility_status(eligibility),
        "invocation_status": _invocation_status(diagnostic_run),
        "rejection_codes": _rejection_codes(eligibility, diagnostic_run, validation),
        "evidence_refs": _evidence_refs(contract, diagnostic_run),
        "read_only": True,
        "not_business_completion": True,
    }
    if diagnostic_run and diagnostic_run.invocation_record:
        payload["task_package_id"] = diagnostic_run.invocation_record.task_package_id
        payload["task_package_hash"] = diagnostic_run.invocation_record.task_package_hash
    if diagnostic_run and diagnostic_run.result_candidate:
        payload["result_id"] = diagnostic_run.result_candidate.result_id
    if validation:
        payload["result_state"] = validation.result_state
        payload["evidence_status"] = validation.evidence.status
        payload["safety_status"] = validation.safety.status
        payload["governed_status"] = validation.governed.status
        payload["business_state_committed"] = validation.business_state_committed
    else:
        payload["business_state_committed"] = False
    return sanitize_private_agent_projection(payload)


def sanitize_private_agent_projection(record: dict[str, Any]) -> dict[str, Any]:
    filtered = {key: value for key, value in record.items() if key in PRIVATE_AGENT_PROJECTION_FIELDS}
    return _redact_value(redact_payload(filtered))


def _eligibility_status(eligibility: Optional[PrivateAgentEligibilityDecision]) -> str:
    if eligibility is None:
        return "not_evaluated"
    return "eligible" if eligibility.accepted else "rejected"


def _invocation_status(diagnostic_run: Optional[PrivateDiagnosticRunResult]) -> str:
    if diagnostic_run is None:
        return "not_invoked"
    return "diagnostic_candidate" if diagnostic_run.accepted else "rejected"


def _rejection_codes(
    eligibility: Optional[PrivateAgentEligibilityDecision],
    diagnostic_run: Optional[PrivateDiagnosticRunResult],
    validation: Optional[PrivateValidationDecision],
) -> list[str]:
    codes: list[str] = []
    if eligibility:
        codes.extend(eligibility.errors)
    if diagnostic_run:
        codes.extend(diagnostic_run.errors)
    if validation:
        codes.extend(validation.evidence.errors)
        codes.extend(validation.safety.errors)
        codes.extend(validation.governed.errors)
    deduped: list[str] = []
    for code in codes:
        if code not in deduped:
            deduped.append(code)
    return deduped


def _evidence_refs(contract: PrivateAgentContract, diagnostic_run: Optional[PrivateDiagnosticRunResult]) -> list[str]:
    refs = [contract.last_review_evidence_ref]
    if diagnostic_run and diagnostic_run.invocation_record:
        refs.extend(diagnostic_run.invocation_record.evidence_refs)
    return [ref for ref in refs if ref]


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str) and _looks_secret(value):
        return "[REDACTED]"
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    return any(marker in lowered for marker in ("authorization", "credential", "password", "private_key", "secret", "token"))


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith("sk-") or any(
        marker in lowered for marker in ("authorization:", "bearer ", "password=", "secret=", "token=")
    )
