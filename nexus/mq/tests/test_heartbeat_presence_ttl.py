from nexus.mq.agent_registry import AgentRegistry
from nexus.mq.tests.test_agent_registry_readiness import _record


def test_heartbeat_ttl_marks_stale_and_blocks_dispatch():
    registry = AgentRegistry([_record(last_heartbeat_at="2026-05-18T00:00:00+00:00", heartbeat_ttl_seconds=10)])

    updated = registry.evaluate_presence(now_at="2026-05-18T00:00:15+00:00")
    decision = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-ttl",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:15+00:00",
    )

    assert updated[0].presence_state == "stale"
    assert decision.accepted is False
    assert "NO_ELIGIBLE_AGENT" in decision.errors
    assert "PRESENCE_NOT_IDLE: stale" in decision.rejected["jarvis"]
