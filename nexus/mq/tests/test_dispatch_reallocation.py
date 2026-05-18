from nexus.mq.agent_registry import AgentRegistry, reallocate_or_dlq_assignment
from nexus.mq.tests.test_agent_registry_readiness import _record


def test_stalled_assignment_reallocates_without_business_commit():
    registry = AgentRegistry(
        [
            _record(agent_id="first", runtime_instance_id="first-runtime"),
            _record(agent_id="second", runtime_instance_id="second-runtime"),
        ]
    )
    assignment = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-realloc",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:00+00:00",
    ).assignment
    assignment.dispatch_state = "stalled"

    reallocated = reallocate_or_dlq_assignment(
        assignment,
        registry,
        now_at="2026-05-18T00:01:00+00:00",
        reason="heartbeat_stale",
    )

    assert reallocated.dispatch_state == "reallocated"
    assert reallocated.assigned_agent_id == "second"
    assert reallocated.reallocation_count == 1
    assert reallocated.not_business_completion is True


def test_stalled_assignment_dlqs_when_no_eligible_agent():
    registry = AgentRegistry([_record(agent_id="first", runtime_instance_id="first-runtime")])
    assignment = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-dlq",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:00+00:00",
    ).assignment

    dlq = reallocate_or_dlq_assignment(
        assignment,
        registry,
        now_at="2026-05-18T00:01:00+00:00",
        reason="no_eligible_agent",
        max_reallocations=0,
    )

    assert dlq.dispatch_state == "dlq"
    assert dlq.last_error_ref == "no_eligible_agent"
    assert any(ref.startswith("dlq://4.19/") for ref in dlq.evidence_refs)
