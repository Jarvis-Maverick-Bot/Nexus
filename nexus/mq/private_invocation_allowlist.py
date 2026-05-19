"""Allowlist-only CLI/API invocation declarations for WBS 7.12."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from nexus.mq.agent_registry_events import secret_material_errors
from nexus.mq.private_agent_contract import AllowedPrivateInvocation, PrivateAgentContract


@dataclass(frozen=True)
class PrivateInvocationRequest:
    invocation_id: str
    invocation_type: str
    command_or_endpoint_ref: str
    args: dict[str, str] = field(default_factory=dict)
    env_refs: list[str] = field(default_factory=list)
    task_package_hash: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateInvocationValidationResult:
    accepted: bool
    invocation: Optional[AllowedPrivateInvocation] = None
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def validate_private_invocation_allowlist(
    contract: PrivateAgentContract,
    request: PrivateInvocationRequest,
) -> PrivateInvocationValidationResult:
    errors: list[str] = []
    if request.not_business_completion is not True:
        errors.append("PRIVATE_INVOCATION_CANNOT_BE_BUSINESS_COMPLETION")
    if not request.task_package_hash:
        errors.append("PRIVATE_INVOCATION_REQUIRES_TASK_PACKAGE_HASH")
    errors.extend(secret_material_errors(request.to_dict(), path="private_invocation_request"))

    invocation = _find_invocation(contract, request.invocation_id)
    if invocation is None:
        return PrivateInvocationValidationResult(
            accepted=False,
            errors=_dedupe([*errors, "PRIVATE_INVOCATION_NOT_ALLOWLISTED"]),
        )

    if request.invocation_type != invocation.invocation_type:
        errors.append("PRIVATE_INVOCATION_TYPE_MISMATCH")
    if request.command_or_endpoint_ref != invocation.command_or_endpoint_ref:
        errors.append("PRIVATE_INVOCATION_TARGET_NOT_ALLOWLISTED")
    errors.extend(_args_errors(invocation, request.args))
    errors.extend(_env_errors(invocation, request.env_refs))
    return PrivateInvocationValidationResult(
        accepted=not errors,
        invocation=invocation if not errors else None,
        errors=_dedupe(errors),
    )


def _find_invocation(contract: PrivateAgentContract, invocation_id: str) -> Optional[AllowedPrivateInvocation]:
    for invocation in contract.allowed_invocations:
        if invocation.invocation_id == invocation_id:
            return invocation
    return None


def _args_errors(invocation: AllowedPrivateInvocation, args: dict[str, str]) -> list[str]:
    errors: list[str] = []
    allowed_schema = invocation.allowed_args
    for key, value in args.items():
        if key not in allowed_schema:
            errors.append(f"PRIVATE_INVOCATION_ARG_NOT_ALLOWLISTED: {key}")
            continue
        allowed_values = allowed_schema.get(key) or []
        if allowed_values and value not in allowed_values:
            errors.append(f"PRIVATE_INVOCATION_ARG_VALUE_NOT_ALLOWLISTED: {key}")
    for key in allowed_schema:
        if key not in args:
            errors.append(f"PRIVATE_INVOCATION_REQUIRED_ARG_MISSING: {key}")
    return errors


def _env_errors(invocation: AllowedPrivateInvocation, env_refs: list[str]) -> list[str]:
    errors: list[str] = []
    allowed_refs = set(invocation.allowed_env_refs)
    forbidden = {item.lower() for item in invocation.forbidden_env_keys}
    for env_ref in env_refs:
        if env_ref not in allowed_refs:
            errors.append(f"PRIVATE_INVOCATION_ENV_REF_NOT_ALLOWLISTED: {env_ref}")
        lowered = env_ref.lower()
        if any(marker in lowered for marker in forbidden):
            errors.append(f"PRIVATE_INVOCATION_ENV_REF_FORBIDDEN: {env_ref}")
    return errors


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
