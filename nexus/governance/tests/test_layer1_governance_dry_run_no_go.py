from __future__ import annotations

from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.layer1_dry_run import REQUIRED_NEGATIVE_FAMILIES, build_negative_fixture_results


APPROVED_PACKAGE_NEGATIVE_FAMILIES = {
    "stale_wbs_source_authority",
    "smb_only_authority",
    "missing_slice010_evidence",
    "workspace_final_status",
    "missing_evaluation_profile",
    "stale_deliverable_evaluation_profile",
    "stale_feedback_metric_policy",
    "workpacket_submitted_state",
    "handoff_controller_execution",
    "direct_ui_approval",
    "local_app_direct_approval",
    "read_only_mutation",
    "monitor_workpacket_execution",
    "runtime_private_agent_invocation",
    "route_activation",
    "adapter_transport_activation",
    "owner_path_call",
    "lower_layer_submission",
    "raw_feedback_mutation",
    "completion_decision_wording",
    "continuity_activation_wording",
    "production_readiness_wording",
    "deploy_readiness_wording",
    "final_pass_wording",
    "projection_as_authority",
    "local_app_view_model_authority",
    "version_mismatch",
    "idempotency_mismatch",
}


def test_cross_component_negative_fixtures_cover_approved_package_no_go_families() -> None:
    observed = {result["family"] for result in build_negative_fixture_results()}

    assert APPROVED_PACKAGE_NEGATIVE_FAMILIES <= observed


def test_cross_component_negative_fixtures_cover_required_no_go_families() -> None:
    results = build_negative_fixture_results()

    assert tuple(result["family"] for result in results) == REQUIRED_NEGATIVE_FAMILIES
    assert all(result["accepted"] is False for result in results)
    assert all(result["error_code"] for result in results)

    write_evidence(
        "negative-fixture-results.json",
        {
            "accepted": True,
            "fixture_count": len(results),
            "results": results,
        },
        slice_id="l1gov-slice-011",
    )


def test_cross_component_negative_fixtures_fail_closed_without_live_execution() -> None:
    results = build_negative_fixture_results()
    allowed_codes = {code.value for code in ErrorCode}

    for result in results:
        assert result["error_code"] in allowed_codes
        assert result["live_execution_invoked"] is False
        assert result["records_appended"] == 0
        assert result["blocked_by"] in (
            "source_authority",
            "workspace_init",
            "standardization",
            "project_execution",
            "dispatch_contract",
            "monitor_hitl",
            "impact_control",
            "delivery_feedback",
            "governance_service",
            "local_app_contract",
        )

    write_evidence(
        "source-authority-fixtures.json",
        {"accepted": True, "families": list(REQUIRED_NEGATIVE_FAMILIES)},
        slice_id="l1gov-slice-011",
    )
