"""Deterministic diagnostic-only private invocation runner for WBS 7.12.

The runner records what an approved diagnostic wrapper would return. It does
not start a process, make HTTP calls, publish to a broker, or mutate business
state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from nexus.mq.private_agent_contract import PrivateAgentContract
from nexus.mq.private_invocation_allowlist import PrivateInvocationRequest, validate_private_invocation_allowlist
from nexus.mq.private_result_candidate import PrivateAgentResultCandidate, PrivateResultOutput
from nexus.mq.private_task_package import PrivateAgentTaskPackage, validate_private_task_package


@dataclass(frozen=True)
class PreparedDiagnosticResult:
    result_id: str
    status_claim: str
    summary: str
    outputs: list[PrivateResultOutput]
    evidence_refs: list[str]
    self_reported_risks: list[str] = field(default_factory=list)
    requested_followup_context: list[str] = field(default_factory=list)
    claims_business_completion: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateDiagnosticInvocationRecord:
    invocation_id: str
    contract_id: str
    contract_revision: int
    task_package_id: str
    task_package_hash: str
    command_or_endpoint_ref: str
    diagnostic_only: bool
    business_execution_allowed: bool
    evidence_refs: list[str]
    read_only: bool = True
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrivateDiagnosticRunResult:
    accepted: bool
    invocation_record: Optional[PrivateDiagnosticInvocationRecord] = None
    result_candidate: Optional[PrivateAgentResultCandidate] = None
    errors: list[str] = field(default_factory=list)
    business_state_committed: bool = False
    not_business_completion: bool = True


def run_private_diagnostic_invocation(
    contract: PrivateAgentContract,
    package: PrivateAgentTaskPackage,
    invocation_request: PrivateInvocationRequest,
    prepared_result: PreparedDiagnosticResult,
    *,
    now_at: str,
) -> PrivateDiagnosticRunResult:
    errors: list[str] = []
    if package.task_kind != "diagnostic":
        errors.append("PRIVATE_DIAGNOSTIC_ONLY")
    package_errors = validate_private_task_package(package, contract=contract, now_at=now_at)
    errors.extend(package_errors)
    allowlist = validate_private_invocation_allowlist(contract, invocation_request)
    errors.extend(allowlist.errors)
    if invocation_request.task_package_hash != package.package_hash:
        errors.append("PRIVATE_INVOCATION_TASK_PACKAGE_HASH_MISMATCH")
    if errors or allowlist.invocation is None:
        return PrivateDiagnosticRunResult(accepted=False, errors=_dedupe(errors))

    record = PrivateDiagnosticInvocationRecord(
        invocation_id=invocation_request.invocation_id,
        contract_id=contract.contract_id,
        contract_revision=contract.contract_revision,
        task_package_id=package.task_package_id,
        task_package_hash=package.package_hash,
        command_or_endpoint_ref=allowlist.invocation.command_or_endpoint_ref,
        diagnostic_only=True,
        business_execution_allowed=False,
        evidence_refs=list(prepared_result.evidence_refs),
    )
    candidate = PrivateAgentResultCandidate(
        result_id=prepared_result.result_id,
        assignment_id=package.assignment_id,
        contract_id=contract.contract_id,
        contract_revision=contract.contract_revision,
        task_package_id=package.task_package_id,
        task_package_hash=package.package_hash,
        invocation_id=invocation_request.invocation_id,
        status_claim=prepared_result.status_claim,
        summary=prepared_result.summary,
        outputs=list(prepared_result.outputs),
        evidence_refs=list(prepared_result.evidence_refs),
        self_reported_risks=list(prepared_result.self_reported_risks),
        requested_followup_context=list(prepared_result.requested_followup_context),
        claims_business_completion=prepared_result.claims_business_completion,
        produced_at=now_at,
    )
    return PrivateDiagnosticRunResult(
        accepted=True,
        invocation_record=record,
        result_candidate=candidate,
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
