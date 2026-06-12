from __future__ import annotations

from nexus.governance.dispatch_contract import (
    validate_dispatch_readiness_inputs,
    validate_layer2_capability_profile,
    validate_layer3_transport_constraint,
)
from nexus.governance.errors import ErrorCode

from ._evidence import write_evidence
from .fixtures.dispatch_contract import (
    kernel_ready_workpacket,
    valid_capability_profile,
    valid_dispatch_context,
    valid_transport_constraint,
)


def test_dispatch_readiness_accepts_kernel_ready_packet_capability_and_transport_refs() -> None:
    result = validate_dispatch_readiness_inputs(
        packet=kernel_ready_workpacket(),
        capability=valid_capability_profile(),
        transport_constraints=(valid_transport_constraint(),),
        context=valid_dispatch_context(),
        kernel_packet_record_ref="kernel-record:packet-ready-000001",
    )

    assert result.accepted is True
    write_evidence("dispatch/kernel-ready-packet-valid.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_readiness_rejects_packet_without_kernel_ready_record() -> None:
    result = validate_dispatch_readiness_inputs(
        packet=kernel_ready_workpacket(),
        capability=valid_capability_profile(),
        transport_constraints=(valid_transport_constraint(),),
        context=valid_dispatch_context(),
        kernel_packet_record_ref="",
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert "Kernel-ready packet record ref is required" in result.blocked_reasons
    write_evidence("dispatch/packet-invalid-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_layer2_capability_profile_rejects_outside_419_baseline() -> None:
    profile = valid_capability_profile(baseline_ref="experimental-runtime")

    result = validate_layer2_capability_profile(profile)

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert "Layer2CapabilityProfileRef must cite 4.19 baseline" in result.blocked_reasons
    write_evidence("dispatch/capability-block.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_layer3_transport_constraint_rejects_ack_as_progress() -> None:
    constraint = valid_transport_constraint(ack_is_progress=True)

    result = validate_layer3_transport_constraint(constraint)

    assert result.accepted is False
    assert result.error_code == ErrorCode.ACK_NOT_ACCEPTANCE
    assert "ACK/progress cannot be treated as Layer 1 progress" in result.blocked_reasons
    write_evidence("dispatch/ack-not-acceptance.json", result.to_evidence(), slice_id="l1gov-slice-005")


def test_dispatch_readiness_rejects_missing_no_go_or_stop_rules() -> None:
    packet = kernel_ready_workpacket(no_go=(), stop_rules=())

    result = validate_dispatch_readiness_inputs(
        packet=packet,
        capability=valid_capability_profile(),
        transport_constraints=(valid_transport_constraint(),),
        context=valid_dispatch_context(),
        kernel_packet_record_ref="kernel-record:packet-ready-000001",
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert "packet no-go and stop rules must be preserved" in result.blocked_reasons


def test_dispatch_readiness_rejects_owner_role_not_in_capability_profile() -> None:
    packet = kernel_ready_workpacket(owner_role="unlisted-owner")

    result = validate_dispatch_readiness_inputs(
        packet=packet,
        capability=valid_capability_profile(eligible_owner_roles=("implementation-agent",)),
        transport_constraints=(valid_transport_constraint(),),
        context=valid_dispatch_context(),
        kernel_packet_record_ref="kernel-record:packet-ready-000001",
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.DISPATCH_RECORD_INVALID
    assert "packet owner_role is not eligible for Layer 2 capability profile" in result.blocked_reasons
    write_evidence("dispatch/owner-role-capability-block.json", result.to_evidence(), slice_id="l1gov-slice-005")
