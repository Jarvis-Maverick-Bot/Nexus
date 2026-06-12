from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.standardization import (
    AmbiguityItem,
    validate_ambiguity_register,
    validate_execution_plan_candidate,
    validate_scope_no_go,
    validate_standardization_output_base,
)

from ._evidence import write_evidence
from .fixtures.standardization import (
    valid_ambiguity_register,
    valid_execution_plan,
    valid_planning_input,
    valid_scope_no_go,
)


def test_standardization_output_requires_common_base_fields() -> None:
    item = valid_planning_input(source_refs=(), workspace_manifest_ref="")

    result = validate_standardization_output_base(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_RECORD_INVALID
    assert result.missing_fields == ("workspace_manifest_ref", "source_refs")
    write_evidence("standardization/common-base-field-block.json", result.to_evidence(), slice_id="l1gov-slice-003")


def test_scope_no_go_requires_paired_scope_and_no_go() -> None:
    item = valid_scope_no_go(no_go=())

    result = validate_scope_no_go(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_RECORD_INVALID
    assert "scope and no-go must be paired" in result.blocked_reasons
    write_evidence("standardization/scope-no-go-pairing-block.json", result.to_evidence(), slice_id="l1gov-slice-003")


def test_critical_open_ambiguity_blocks_approval_readiness() -> None:
    item = valid_ambiguity_register(
        ambiguity_items=(
            AmbiguityItem(
                ambiguity_id="amb-critical",
                severity="critical",
                owner="Nova",
                required_decision="confirm approval authority",
                status="open",
            ),
        )
    )

    result = validate_ambiguity_register(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_RECORD_INVALID
    assert "critical ambiguity remains open: amb-critical" in result.blocked_reasons
    write_evidence(
        "standardization/critical-ambiguity-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )


def test_execution_plan_candidate_requires_all_review_refs() -> None:
    item = valid_execution_plan(evidence_map_ref="")

    result = validate_execution_plan_candidate(item)

    assert result.accepted is False
    assert result.error_code == ErrorCode.STANDARDIZATION_RECORD_INVALID
    assert result.missing_fields == ("evidence_map_ref",)
    write_evidence(
        "standardization/execution-plan-review-ref-block.json",
        result.to_evidence(),
        slice_id="l1gov-slice-003",
    )
