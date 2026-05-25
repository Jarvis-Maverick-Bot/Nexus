"""Thin endpoint contract validation for Layer 3 daemon clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors


@dataclass
class ThinEndpointValidation:
    valid: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "not_business_completion": self.not_business_completion,
        }


def validate_thin_endpoint_contract(contract: dict[str, Any]) -> ThinEndpointValidation:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ThinEndpointValidation(valid=False, errors=["ENDPOINT_CONTRACT_MUST_BE_OBJECT"])

    for field_name in ("endpoint_id", "runtime_instance_id", "correlation_id", "idempotency_key"):
        if not contract.get(field_name):
            errors.append(f"MISSING_REQUIRED_FIELD: {field_name}")

    allowed_operations = contract.get("allowed_operations")
    if not isinstance(allowed_operations, list) or not allowed_operations:
        errors.append("MISSING_REQUIRED_FIELD: allowed_operations")
    else:
        forbidden = set(allowed_operations) & {"retry", "dlq", "replay", "business_complete", "broker_setup"}
        for operation in sorted(forbidden):
            errors.append(f"ENDPOINT_OPERATION_OUT_OF_SCOPE: {operation}")

    if "retry_policy" in contract or contract.get("owns_retry_policy") is True:
        errors.append("ENDPOINT_MUST_NOT_OWN_RETRY_POLICY")
    if "dlq_subject" in contract or contract.get("owns_dlq_policy") is True:
        errors.append("ENDPOINT_MUST_NOT_OWN_DLQ_POLICY")
    if "replay_decision" in contract or contract.get("owns_replay_policy") is True:
        errors.append("ENDPOINT_MUST_NOT_OWN_REPLAY_DECISION")
    if contract.get("business_completion") is True:
        errors.append("ENDPOINT_CANNOT_CLAIM_BUSINESS_COMPLETION")
    if contract.get("not_business_completion") is not True:
        errors.append("NOT_BUSINESS_COMPLETION_REQUIRED")

    original_correlation = contract.get("original_correlation_id") or contract.get("correlation_id")
    returned_correlation = contract.get("returned_correlation_id") or contract.get("correlation_id")
    if original_correlation and returned_correlation and original_correlation != returned_correlation:
        errors.append("ENDPOINT_MUST_PRESERVE_CORRELATION_ID")

    errors.extend(secret_material_errors(contract, path="endpoint"))
    return ThinEndpointValidation(valid=not errors, errors=list(dict.fromkeys(errors)))
