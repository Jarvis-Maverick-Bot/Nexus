"""P6-32 through P6-38 goal-driven Command_Message coverage."""

from __future__ import annotations

import os

from nexus.mq.ack_policy import AckPolicy
from nexus.mq.business_message import BusinessMessageEmitter
from nexus.mq.command_handler import CommandHandler
from nexus.mq.commit_boundary import CommitBoundary
from nexus.mq.coordination_runtime import CoordinationRuntime
from nexus.mq.idempotency_store import IdempotencyStore
from nexus.mq.message_contracts import build_execution_envelope, validate_execution_message


def _identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents.yaml")
    )


def _goal_payload(**overrides) -> dict:
    payload = {
        "command_name": "Goal_Driven_Command",
        "goal_statement": "Prepare the bounded goal-driven command implementation patch.",
        "measurable_done_condition": "Focused goal-driven command tests pass with evidence.",
        "constraints": ["preserve existing Command_Message semantics"],
        "allowed_write_scope": ["nexus/mq/payloads.py", "nexus/mq/message_contracts.py"],
        "allowed_tool_scope": ["pytest focused goal-driven command tests"],
        "forbidden_actions": ["do not add a new message family"],
        "source_authority_refs": ["shared-docs://THUNDER_GOAL_DRIVEN_COMMANDS_HANDOFF_V0_1"],
        "source_authority_gap": None,
        "validation_commands_or_checks": ["python -m pytest nexus/mq/tests/test_goal_driven_commands.py -q"],
        "required_evidence_refs": ["pytest output for P6-32 through P6-38"],
        "stop_conditions": ["authority, scope, validation, or done condition becomes ambiguous"],
        "escalation_route_ref": "alex://goal-driven-command-escalation",
        "progress_record_ref": None,
    }
    payload.update(overrides)
    return payload


def _goal_envelope(payload: dict | None = None) -> dict:
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-goal-command-001",
        workflow_type="goal_driven",
        workflow_version="1.0",
        producer="maverick",
        payload=payload or _goal_payload(),
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        idempotency_key="idem-goal-command-001",
        correlation_id="corr-goal-command-001",
    ).to_dict()


def _ordinary_command_envelope() -> dict:
    return build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-ordinary-command-001",
        workflow_type="standard",
        workflow_version="1.0",
        producer="maverick",
        payload={
            "command_name": "dispatch",
            "target_handler": "runtime.dispatch",
            "completion_event_type": "command.dispatched",
        },
        source_agent_id="maverick",
        source_runtime_instance_id="maverick-windows-main-20260507",
        source_role="maverick",
        authority_scope="workflow.command",
        target_agent_id="maverick",
        reply_to_subject="agent.maverick.callbacks",
        idempotency_key="idem-ordinary-command-001",
        correlation_id="corr-ordinary-command-001",
    ).to_dict()


def test_goal_command_requires_done_condition():
    envelope = _goal_envelope(_goal_payload(measurable_done_condition=""))

    result = validate_execution_message(envelope)

    assert result.valid is False
    assert "DONE_CONDITION_MISSING" in result.errors


def test_goal_command_requires_source_gap_when_no_refs():
    envelope = _goal_envelope(_goal_payload(source_authority_refs=[], source_authority_gap=None))

    result = validate_execution_message(envelope)

    assert result.valid is False
    assert "SOURCE_AUTHORITY_UNDECLARED" in result.errors


def test_goal_command_rejects_unbounded_scope(tmp_path):
    envelope = _goal_envelope(_goal_payload(allowed_write_scope=None, allowed_tool_scope=[]))
    runtime = CoordinationRuntime.from_paths(
        runtime_id="maverick-runtime-goal-p6-34",
        agent_id="maverick",
        role="maverick",
        db_path=tmp_path / "goal-p6-34.sqlite3",
        identity_yaml_path=_identity_config_path(),
    )
    runtime.startup()

    rejected = runtime.intake_inbound_message("agent.maverick.inbox", envelope)
    read_only = validate_execution_message(
        _goal_envelope(_goal_payload(allowed_write_scope=[], allowed_tool_scope=[]))
    )
    runtime.close()

    assert rejected.valid is False
    assert rejected.ack_allowed is False
    assert rejected.broker_action == "REJECT"
    assert rejected.failure_class == "IF-02"
    assert "GOAL_SCOPE_UNBOUNDED" in rejected.errors
    assert read_only.valid is True


def test_goal_command_requires_validation_contract():
    envelope = _goal_envelope(
        _goal_payload(validation_commands_or_checks=[], required_evidence_refs=[])
    )

    result = validate_execution_message(envelope)

    assert result.valid is False
    assert "VALIDATION_CONTRACT_MISSING" in result.errors


def test_goal_command_requires_stop_conditions_and_escalation_route():
    envelope = _goal_envelope(_goal_payload(stop_conditions=[], escalation_route_ref=""))

    result = validate_execution_message(envelope)

    assert result.valid is False
    assert "ESCALATION_ROUTE_MISSING" in result.errors


def test_goal_command_escalates_on_ambiguity():
    idempotency_store = IdempotencyStore()
    commit_boundary = CommitBoundary()
    handler = CommandHandler(idempotency_store, commit_boundary, AckPolicy())
    envelope = _goal_envelope()

    result = handler.handle(
        envelope,
        execute_command=lambda _payload: {
            "status": "stopped_for_escalation",
            "ambiguity_reason": "scope became ambiguous during bounded inference",
            "escalation_route_ref": "alex://goal-driven-command-escalation",
        },
    )

    assert result.status == "rejected"
    assert "GOAL_COMMAND_AMBIGUITY" in (result.error or "")
    assert commit_boundary.get_commit_log() == []
    assert idempotency_store.get_record(envelope["idempotency_key"]) is None


def test_ordinary_command_ambiguous_status_is_not_goal_ambiguity():
    idempotency_store = IdempotencyStore()
    commit_boundary = CommitBoundary()
    handler = CommandHandler(idempotency_store, commit_boundary, AckPolicy())
    envelope = _ordinary_command_envelope()

    result = handler.handle(
        envelope,
        execute_command=lambda _payload: {
            "status": "ambiguous",
            "evidence_refs": ["evidence://ordinary/ambiguous-status"],
            "transition_request": {"new_state": "ordinary_candidate_progress"},
        },
    )

    assert result.status == "committed"
    assert "GOAL_COMMAND_AMBIGUITY" not in (result.error or "")
    assert commit_boundary.get_current_state(envelope["workflow_instance_id"]) == "ordinary_candidate_progress"
    assert idempotency_store.get_record(envelope["idempotency_key"]) is not None


def test_goal_command_handler_success_not_business_completion():
    idempotency_store = IdempotencyStore()
    commit_boundary = CommitBoundary()
    business_emitter = BusinessMessageEmitter()
    handler = CommandHandler(idempotency_store, commit_boundary, AckPolicy())
    envelope = _goal_envelope()

    result = handler.handle(
        envelope,
        execute_command=lambda _payload: {
            "ok": True,
            "evidence_refs": ["evidence://goal-driven/p6-38"],
            "transition_request": {"new_state": "candidate_progress"},
        },
    )

    assert result.status == "committed"
    assert commit_boundary.get_current_state(envelope["workflow_instance_id"]) == "candidate_progress"
    assert business_emitter.get_emitted() == []
