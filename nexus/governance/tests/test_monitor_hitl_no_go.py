from __future__ import annotations

import pytest

from nexus.governance.errors import ErrorCode
from nexus.governance.monitor_hitl import validate_human_review_task, validate_monitor_hitl_command
from nexus.governance.no_go import NoGoBoundaryPolicy

from ._evidence import write_evidence
from .fixtures.monitor_hitl import valid_create_review_task_command, valid_review_task


@pytest.mark.parametrize(
    "action",
    (
        "monitor_direct_ui_approval",
        "monitor_notification_as_decision",
        "monitor_status_card_approval",
        "monitor_chat_approval",
        "monitor_controller_approval",
        "monitor_dispatch_ack_acceptance",
        "monitor_runtime_live_invocation",
        "monitor_dispatch_execution",
        "monitor_direct_419_controller_call",
        "monitor_adapter_transport_route_activation",
        "monitor_workpacket_execution",
        "monitor_delivery_feedback_extraction",
        "monitor_impact_control_implementation",
        "monitor_delivery_completion",
        "monitor_production_readiness",
        "monitor_final_pass",
    ),
)
def test_monitor_no_go_actions_are_blocked(action: str) -> None:
    result = NoGoBoundaryPolicy.default().evaluate({"action": action})

    assert result.blocked is True
    assert result.error_code is not None
    write_evidence(f"no-go/{action}.json", result.to_evidence(), slice_id="l1gov-slice-006")


@pytest.mark.parametrize("trigger_type", ("direct_ui_approval", "notification_as_decision", "status_card_approval"))
def test_review_task_rejects_direct_approval_triggers(trigger_type: str) -> None:
    result = validate_human_review_task(valid_review_task(trigger_type=trigger_type))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


@pytest.mark.parametrize(
    "forbidden_output",
    (
        "final_pass",
        "delivery_complete",
        "production_ready",
        "runtime dispatch",
        "runtime_dispatch",
        "dispatch",
        "controller call",
        "controller_call",
        "controller request",
        "controller action",
        "private-agent invocation",
        "runtime invocation",
        "adapter call",
        "route activation",
        "workpacket execution",
        "workpacket_execution",
    ),
)
def test_create_review_task_command_rejects_forbidden_output_terms(forbidden_output: str) -> None:
    command = valid_create_review_task_command()
    command.payload["expected_outputs"] = (forbidden_output,)

    result = validate_monitor_hitl_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
    write_evidence(
        f"monitor-hitl/forbidden-term-{forbidden_output.replace(' ', '-').replace('_', '-')}.json",
        result.to_evidence(),
        slice_id="l1gov-slice-006",
    )


@pytest.mark.parametrize(
    ("field_name", "text"),
    (
        ("expected_outputs", "please perform controller execution now"),
        ("expected_outputs", "perform actual dispatch"),
        ("notes", "this would require runtime invocation by a private agent"),
        ("notes", "please dispatch now"),
        ("notes", "please perform dispatch execution now"),
        ("notes", "please execute dispatch now"),
        ("notes", "please activate route now"),
        ("notes", "please execute workpacket now"),
    ),
)
def test_create_review_task_command_rejects_sentence_shaped_forbidden_intent(
    field_name: str,
    text: str,
) -> None:
    command = valid_create_review_task_command()
    command.payload[field_name] = (text,) if field_name == "expected_outputs" else text

    result = validate_monitor_hitl_command(command)

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY


@pytest.mark.parametrize(
    ("field_name", "text"),
    (
        ("decision_question", "Can the reviewer approve production readiness after this check?"),
        ("recommended_next_action", "please perform controller execution now"),
    ),
)
def test_review_task_rejects_sentence_shaped_forbidden_intent(field_name: str, text: str) -> None:
    result = validate_human_review_task(valid_review_task(**{field_name: text}))

    assert result.accepted is False
    assert result.error_code == ErrorCode.NO_GO_BOUNDARY
