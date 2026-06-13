from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.kernel import AggregateState, GovernanceKernel
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.service_facade import (
    BaselineEntryCommand,
    GovernanceServiceFacade,
    ServiceOutcomeStatus,
    mediate_baseline_entry_command,
    validate_baseline_entry_command,
)
from nexus.governance.tests.test_source_authority import valid_manifest

from ._evidence import write_evidence
from .fixtures.service_facade import SERVICE_SOURCE_REFS, service_actor


def baseline_entry(**overrides: object) -> BaselineEntryCommand:
    values = {
        "component_output_ref": "component-output:delivery-feedback:001",
        "workitem_type": "delivery_feedback",
        "subtype": "completion_continuity_packet",
        "evidence_refs": ("evidence:delivery-feedback:001",),
        "decision_ref": "HumanDecision:triage-approved",
        "expected_state": "completion_continuity_review_requested",
        "expected_version": 12,
        "idempotency_key": "baseline-entry-001",
        "source_refs": SERVICE_SOURCE_REFS,
        "mediated_by_service": True,
    }
    values.update(overrides)
    return BaselineEntryCommand(**values)


def baseline_service(kernel: GovernanceKernel | None = None) -> GovernanceServiceFacade:
    return GovernanceServiceFacade(
        source_manifest=valid_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=kernel or baseline_kernel(),
    )


def baseline_kernel() -> GovernanceKernel:
    return GovernanceKernel(
        state=AggregateState(
            aggregate_id="layer1-governance",
            state="completion_continuity_review_requested",
            version=12,
            authority_refs=SERVICE_SOURCE_REFS,
        )
    )


def test_valid_baseline_entry_command_accepts() -> None:
    result = validate_baseline_entry_command(baseline_entry())

    assert result.accepted is True
    write_evidence("baseline-mediation/baseline-entry-valid.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_baseline_entry_without_service_mediation_rejects() -> None:
    result = validate_baseline_entry_command(baseline_entry(mediated_by_service=False))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("baseline-mediation/component-bypass-reject.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_baseline_entry_rejects_unknown_type_or_subtype() -> None:
    for entry in (
        baseline_entry(workitem_type="user_defined_baseline"),
        baseline_entry(subtype="runtime_dispatch_result"),
    ):
        result = validate_baseline_entry_command(entry)

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence("baseline-mediation/unknown-subtype-reject.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_baseline_entry_rejects_missing_human_decision_when_gated() -> None:
    result = validate_baseline_entry_command(baseline_entry(decision_ref=""))

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    write_evidence("baseline-mediation/missing-human-decision-reject.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_mediate_baseline_entry_appends_kernel_record() -> None:
    kernel = baseline_kernel()
    command = mediate_baseline_entry_command(
        actor=service_actor(),
        authority_refs=SERVICE_SOURCE_REFS,
        baseline_entry=baseline_entry(),
    )

    response = baseline_service(kernel=kernel).handle(command)

    assert response.status == ServiceOutcomeStatus.ACCEPTED
    assert response.kernel_record_ref == "krn-000001"
    assert kernel.state.state == "baseline_entry_recorded"
    assert len(kernel.records) == 1


def test_stale_baseline_entry_rejects_without_kernel_append() -> None:
    kernel = baseline_kernel()
    command = mediate_baseline_entry_command(
        actor=service_actor(),
        authority_refs=SERVICE_SOURCE_REFS,
        baseline_entry=baseline_entry(expected_version=11),
    )

    response = baseline_service(kernel=kernel).handle(command)

    assert response.status == ServiceOutcomeStatus.STALE
    assert response.error_code == ErrorCode.STALE_EXPECTED_VERSION
    assert len(kernel.records) == 0
    write_evidence("service-facade/kernel-boundary-no-append-on-reject.json", response.to_evidence(), slice_id="l1gov-slice-009")
