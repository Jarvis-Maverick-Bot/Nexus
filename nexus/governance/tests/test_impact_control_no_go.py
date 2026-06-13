from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence


@pytest.mark.parametrize(
    ("action", "expected_code"),
    (
        ("impact_direct_419_controller_call", ErrorCode.NO_GO_BOUNDARY),
        ("impact_direct_35_controller_call", ErrorCode.NO_GO_BOUNDARY),
        ("impact_owner_path_call", ErrorCode.NO_GO_BOUNDARY),
        ("impact_adapter_transport_route_activation", ErrorCode.NO_GO_BOUNDARY),
        ("impact_workpacket_execution", ErrorCode.NO_GO_BOUNDARY),
        ("impact_dispatch_execution", ErrorCode.NO_GO_BOUNDARY),
        ("impact_runtime_live_invocation", ErrorCode.NO_GO_BOUNDARY),
        ("impact_lower_layer_submission", ErrorCode.NO_GO_BOUNDARY),
        ("impact_workaround_without_decision", ErrorCode.MISSING_HUMAN_DECISION),
        ("impact_delivery_completion", ErrorCode.NO_GO_BOUNDARY),
        ("impact_production_readiness", ErrorCode.NO_GO_BOUNDARY),
        ("impact_final_pass", ErrorCode.NO_GO_BOUNDARY),
    ),
)
def test_impact_control_no_go_actions_are_blocked(action: str, expected_code: ErrorCode) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code == expected_code
    write_evidence(
        f"no-go/{action.replace('_', '-')}.json",
        result.to_evidence(),
        slice_id="l1gov-slice-007",
    )
