from __future__ import annotations

from ._evidence import write_evidence
from .fixtures.layer1_dry_run import POSITIVE_COMPONENTS, build_positive_dry_run_trace


def test_cross_component_dry_run_composes_slice_001_through_010_contracts() -> None:
    trace = build_positive_dry_run_trace()

    assert trace["accepted"] is True
    assert trace["terminal_state"] == "dry_run_evidence_ready"
    assert trace["live_execution_invoked"] is False
    assert trace["canonical_authority"] == "GovernanceKernel"
    assert trace["service_boundary"] == "GovernanceService"
    assert tuple(step["component"] for step in trace["steps"]) == POSITIVE_COMPONENTS
    assert all(step["accepted"] is True for step in trace["steps"])
    assert all(step["mode"] == "deterministic_fixture" for step in trace["steps"])

    write_evidence("positive-dry-run-result.json", trace, slice_id="l1gov-slice-011")


def test_cross_component_dry_run_trace_records_authority_contract_and_evidence_mapping() -> None:
    trace = build_positive_dry_run_trace()

    for step in trace["steps"]:
        assert step["source_refs"]
        assert step["contract_refs"]
        assert step["evidence_id"].startswith("l1gov-slice-011/")
        assert step["error_code"] is None

    write_evidence(
        "dry-run-trace.json",
        {
            "accepted": trace["accepted"],
            "step_count": len(trace["steps"]),
            "steps": trace["steps"],
        },
        slice_id="l1gov-slice-011",
    )
