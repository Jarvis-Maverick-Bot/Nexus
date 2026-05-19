"""Forbidden-context and redaction policy for private-agent packages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.private_agent_contract import DEFAULT_FORBIDDEN_CONTEXT, PrivateAgentContract


ALLOWED_INPUT_CLASSIFICATIONS = {"public", "project_limited", "redacted", "diagnostic_metadata"}
REDACTION_REQUIRED_CLASSIFICATIONS = {"project_limited", "redacted"}


@dataclass(frozen=True)
class PrivatePackageInput:
    ref: str
    classification: str
    hash: str
    context_class: str
    redaction_manifest_ref: str = ""
    privacy_scope: str = "project"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateContextPolicyResult:
    accepted: bool
    allowed_inputs: list[PrivatePackageInput] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def evaluate_private_context_policy(
    contract: PrivateAgentContract,
    inputs: list[PrivatePackageInput],
) -> PrivateContextPolicyResult:
    errors: list[str] = []
    allowed: list[PrivatePackageInput] = []
    forbidden = set(contract.forbidden_context or DEFAULT_FORBIDDEN_CONTEXT)
    for item in inputs:
        item_errors = _input_errors(contract, item, forbidden_context=forbidden)
        if item_errors:
            errors.extend(item_errors)
        else:
            allowed.append(item)
    return PrivateContextPolicyResult(
        accepted=not errors,
        allowed_inputs=allowed if not errors else [],
        errors=_dedupe(errors),
    )


def redaction_manifest_for(inputs: list[PrivatePackageInput]) -> dict[str, Any]:
    return {
        "schema_version": "4.19.private_agent_redaction_manifest.v1",
        "entries": [
            {
                "ref": item.ref,
                "classification": item.classification,
                "hash": item.hash,
                "redaction_manifest_ref": item.redaction_manifest_ref,
                "context_class": item.context_class,
            }
            for item in inputs
        ],
        "contains_sensitive_material": False,
        "contains_full_repo": False,
        "contains_raw_memory": False,
        "not_business_completion": True,
    }


def _input_errors(
    contract: PrivateAgentContract,
    item: PrivatePackageInput,
    *,
    forbidden_context: set[str],
) -> list[str]:
    errors: list[str] = []
    if not item.ref:
        errors.append("PRIVATE_INPUT_REF_REQUIRED")
    if item.classification not in ALLOWED_INPUT_CLASSIFICATIONS:
        errors.append(f"PRIVATE_INPUT_CLASSIFICATION_INVALID: {item.classification}")
    if not item.hash:
        errors.append("PRIVATE_INPUT_HASH_REQUIRED")
    if item.context_class in forbidden_context:
        errors.append(f"PRIVATE_FORBIDDEN_CONTEXT_BLOCKED: {item.context_class}")
    if item.privacy_scope not in contract.privacy_scope:
        errors.append("PRIVATE_INPUT_PRIVACY_SCOPE_MISMATCH")
    if item.classification in REDACTION_REQUIRED_CLASSIFICATIONS and not item.redaction_manifest_ref:
        errors.append("PRIVATE_REDACTION_MANIFEST_REQUIRED")
    errors.extend(secret_material_errors(item.to_dict(), path="private_package_input"))
    return errors


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
