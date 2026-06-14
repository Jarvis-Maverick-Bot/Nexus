from __future__ import annotations

from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.layer1_dry_run import REQUIRED_NEGATIVE_FAMILIES, build_negative_fixture_results


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
