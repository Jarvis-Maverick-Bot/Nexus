from nexus.mq.startup_packet import StartupPacketRecord, validate_startup_packet, verify_startup_packet_readiness


def _packet(**overrides):
    data = {
        "packet_id": "packet-001",
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "role_seat": "implementation",
        "active_objective": "Implement bounded 4.19 slice",
        "measurable_first_task": "Run pre-edit status check",
        "live_decisions": ["use read-model first"],
        "deprecated_reference_only": [],
        "no_go_scope": ["deployment", "live runtime mutation"],
        "source_authority_refs": ["shared-docs://4.19/refreshed"],
        "message_bus_access_expectations": {"ack_policy": "durable_intake_only"},
        "current_project_state": "WBS 5.2 authorized",
        "required_skills": ["mq"],
        "required_memory_surfaces": ["approved package"],
        "evidence_requirements": ["readiness probe"],
        "reply_format_ref": "report://thunder",
        "stop_conditions": ["ambiguous authority", "scope breach"],
        "issued_at": "2026-05-18T00:00:00+00:00",
    }
    data.update(overrides)
    return StartupPacketRecord(**data)


def test_startup_packet_requires_current_source_and_stop_conditions():
    result = validate_startup_packet(_packet(active_objective="", source_authority_refs=[], stop_conditions=[]))

    assert result.valid is False
    assert "MISSING_ACTIVE_OBJECTIVE" in result.errors
    assert "MISSING_SOURCE_AUTHORITY" in result.errors
    assert "MISSING_STOP_CONDITIONS" in result.errors


def test_startup_packet_ack_alone_is_not_readiness():
    packet = _packet()

    no_evidence = verify_startup_packet_readiness(packet, readiness_evidence_refs=[])
    ready = verify_startup_packet_readiness(packet, readiness_evidence_refs=["evidence://readiness/jarvis"])

    assert no_evidence.valid is False
    assert "MISSING_READINESS_EVIDENCE" in no_evidence.errors
    assert ready.valid is True
    assert ready.evidence_refs == ["evidence://readiness/jarvis"]
