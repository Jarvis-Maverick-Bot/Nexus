from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.service_facade import validate_service_command_envelope

from ._evidence import write_evidence
from .fixtures.service_facade import service_command


def test_impact_sensitive_command_requires_impact_assessment_ref() -> None:
    command = service_command(payload={"impact_surfaces": ("scope", "authority"), "proposed_action": "revise baseline"})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.IMPACT_CONTROL_RECORD_INVALID
    write_evidence("service-facade/impact-preflight-required.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_impact_sensitive_command_accepts_with_impact_assessment_ref() -> None:
    command = service_command(
        payload={
            "impact_surfaces": ("scope",),
            "impact_assessment_ref": "ImpactAssessment:allowed-local",
            "proposed_action": "prepare governed candidate",
        }
    )

    result = validate_service_command_envelope(command)

    assert result.accepted is True


def test_hitl_required_command_requires_human_decision_ref() -> None:
    command = service_command(payload={"review_required": True, "requested_action": "approve baseline"})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.MISSING_HUMAN_DECISION
    write_evidence("service-facade/hitl-routing-required.json", result.to_evidence(), slice_id="l1gov-slice-009")


def test_direct_ui_approval_rejects_as_no_go() -> None:
    command = service_command(payload={"requested_action": "direct_ui_approval"})

    result = validate_service_command_envelope(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_completion_production_final_pass_terms_reject() -> None:
    for text in (
        "complete project",
        "continuity activation",
        "production readiness",
        "deploy to production",
        "final pass",
    ):
        result = validate_service_command_envelope(service_command(payload={"operator_note": text}))

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY


def test_cache_authority_and_direct_canonical_mutation_reject() -> None:
    for payload in (
        {"authorization_source": "app cache", "authority_source": "cache"},
        {"requested_action": "direct canonical mutation outside kernel"},
        {"requested_action": "kernel bypass"},
    ):
        result = validate_service_command_envelope(service_command(payload=payload))

        assert result.accepted is False
        assert result.error_code == ErrorCode.NO_GO_BOUNDARY
