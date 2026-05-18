from nexus.mq.agent_registry import AgentRegistry, AgentRegistryRecord, dispatch_ineligibility_reasons


def _record(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "role": "implementation",
        "owner_principal_id": "principal:jarvis-owner",
        "runtime_type": "local_skeleton",
        "channel_bindings": ["agent.jarvis.inbox"],
        "capabilities": ["implementation"],
        "authority_scopes": ["workflow.command"],
        "allowed_task_boundaries": ["implementation"],
        "initialization_status": "ready",
        "registry_status": "active",
        "presence_state": "idle",
        "heartbeat_ttl_seconds": 60,
        "last_heartbeat_at": "2026-05-18T00:00:00+00:00",
        "current_assignment_refs": [],
        "protocol_versions_supported": ["3.5", "4.19"],
        "trust_material_ref": "local:nats-agent-protocol",
        "startup_packet_ref": "startup-packet://jarvis",
        "readiness_evidence_ref": "evidence://readiness/jarvis",
        "startup_packet_expires_at": "2026-05-18T01:00:00+00:00",
        "created_at": "2026-05-18T00:00:00+00:00",
        "updated_at": "2026-05-18T00:00:00+00:00",
        "privacy_scopes": ["project"],
    }
    data.update(overrides)
    return AgentRegistryRecord(**data)


def test_registry_ready_requires_packet_and_evidence():
    record = _record(startup_packet_ref=None, readiness_evidence_ref=None)

    reasons = dispatch_ineligibility_reasons(
        record,
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:30:00+00:00",
    )

    assert "READINESS_EVIDENCE_MISSING" in reasons


def test_registry_excludes_quarantined_stale_or_online_only_agents():
    registry = AgentRegistry(
        [
            _record(agent_id="ready", runtime_instance_id="ready-runtime"),
            _record(agent_id="stale", runtime_instance_id="stale-runtime", last_heartbeat_at="2026-05-18T00:00:00+00:00"),
            _record(agent_id="online-only", runtime_instance_id="online-runtime", presence_state="online"),
            _record(agent_id="quarantined", runtime_instance_id="q-runtime", initialization_status="quarantined"),
        ]
    )

    decision = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-001",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:00:30+00:00",
    )

    assert decision.accepted is True
    assert decision.assignment.assigned_agent_id == "ready"
    assert "PRESENCE_NOT_IDLE: online" in decision.rejected["online-only"]
    assert "INITIALIZATION_NOT_READY: quarantined" in decision.rejected["quarantined"]


def test_expired_startup_packet_blocks_normal_dispatch():
    registry = AgentRegistry(
        [
            _record(
                agent_id="expired",
                runtime_instance_id="expired-runtime",
                startup_packet_expires_at="2026-05-18T00:05:00+00:00",
            )
        ]
    )

    decision = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-expired-startup",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:10:00+00:00",
    )

    assert decision.accepted is False
    assert "NO_ELIGIBLE_AGENT" in decision.errors
    assert "STARTUP_PACKET_EXPIRED" in decision.rejected["expired"]


def test_invalid_startup_packet_freshness_blocks_dispatch_without_exception():
    registry = AgentRegistry(
        [
            _record(
                agent_id="invalid-freshness",
                runtime_instance_id="invalid-freshness-runtime",
                startup_packet_expires_at="not-a-timestamp",
            )
        ]
    )

    decision = registry.assign_work(
        work_ref="implementation",
        message_envelope_ref="envelope://cmd-invalid-startup",
        required_capability="implementation",
        required_authority_scope="workflow.command",
        required_privacy_scope="project",
        allowed_task_boundary="implementation",
        now_at="2026-05-18T00:10:00+00:00",
    )

    assert decision.accepted is False
    assert "NO_ELIGIBLE_AGENT" in decision.errors
    assert "STARTUP_PACKET_FRESHNESS_INVALID" in decision.rejected["invalid-freshness"]
