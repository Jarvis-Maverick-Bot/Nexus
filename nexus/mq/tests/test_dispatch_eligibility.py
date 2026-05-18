from nexus.mq.agent_registry import AgentRegistry
from nexus.mq.runtime_adapter_contract import RuntimeAdapterEvent, validate_runtime_adapter_event
from nexus.mq.tests.test_agent_registry_readiness import _record


def test_dispatch_selects_idle_capable_authorized_agent():
    registry = AgentRegistry(
        [
            _record(agent_id="busy", runtime_instance_id="busy-runtime", presence_state="busy"),
            _record(agent_id="unauthorized", runtime_instance_id="unauth-runtime", authority_scopes=["workflow.review"]),
            _record(agent_id="ready", runtime_instance_id="ready-runtime", load_score=0.2),
        ]
    )

    decision = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-dispatch",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:00+00:00",
    )

    assert decision.accepted is True
    assert decision.assignment.assigned_agent_id == "ready"
    assert "PRESENCE_NOT_IDLE: busy" in decision.rejected["busy"]
    assert "AUTHORITY_SCOPE_MISMATCH: workflow.command" in decision.rejected["unauthorized"]
    assert decision.assignment.not_business_completion is True


def test_runtime_adapter_result_must_match_assignment_source():
    registry = AgentRegistry([_record(agent_id="ready", runtime_instance_id="ready-runtime")])
    assignment = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-dispatch",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:00+00:00",
    ).assignment

    valid = validate_runtime_adapter_event(
        RuntimeAdapterEvent(
            adapter_id="adapter-local",
            adapter_type="local",
            protocol_version="4.19.runtime_adapter.v1",
            event_type="result",
            agent_id="ready",
            runtime_instance_id="ready-runtime",
            message_id="msg-result",
            correlation_id="corr-result",
            assignment_id=assignment.assignment_id,
            payload={"status": "completed_candidate"},
        ),
        assignment=assignment,
    )
    mismatch = validate_runtime_adapter_event(
        RuntimeAdapterEvent(
            adapter_id="adapter-local",
            adapter_type="local",
            protocol_version="4.19.runtime_adapter.v1",
            event_type="result",
            agent_id="other",
            runtime_instance_id="other-runtime",
            message_id="msg-result",
            correlation_id="corr-result",
            assignment_id=assignment.assignment_id,
            payload={"status": "completed_candidate"},
        ),
        assignment=assignment,
    )

    assert valid.valid is True
    assert "ASSIGNED_AGENT_MISMATCH" in mismatch.errors
    assert "ASSIGNED_RUNTIME_MISMATCH" in mismatch.errors
