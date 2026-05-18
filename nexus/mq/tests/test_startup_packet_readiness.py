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
        "valid_for_seconds": 3600,
    }
    data.update(overrides)
    return StartupPacketRecord(**data)


def test_startup_packet_requires_current_source_and_stop_conditions():
    result = validate_startup_packet(
        _packet(active_objective="", source_authority_refs=[], stop_conditions=[]),
        now_at="2026-05-18T00:10:00+00:00",
    )

    assert result.valid is False
    assert "MISSING_ACTIVE_OBJECTIVE" in result.errors
    assert "MISSING_SOURCE_AUTHORITY" in result.errors
    assert "MISSING_STOP_CONDITIONS" in result.errors


def test_startup_packet_ack_alone_is_not_readiness():
    packet = _packet()

    no_evidence = verify_startup_packet_readiness(
        packet,
        readiness_evidence_refs=[],
        now_at="2026-05-18T00:10:00+00:00",
    )
    ready = verify_startup_packet_readiness(
        packet,
        readiness_evidence_refs=["evidence://readiness/jarvis"],
        now_at="2026-05-18T00:10:00+00:00",
    )

    assert no_evidence.valid is False
    assert "MISSING_READINESS_EVIDENCE" in no_evidence.errors
    assert ready.valid is True
    assert ready.evidence_refs == ["evidence://readiness/jarvis"]


def test_fresh_startup_packet_with_readiness_evidence_is_valid():
    packet = _packet(expires_at="2026-05-18T01:00:00+00:00", valid_for_seconds=None)

    result = verify_startup_packet_readiness(
        packet,
        readiness_evidence_refs=["evidence://readiness/jarvis"],
        now_at="2026-05-18T00:30:00+00:00",
    )

    assert result.valid is True
    assert result.errors == []


def test_expired_startup_packet_is_invalid():
    expired_by_expires_at = verify_startup_packet_readiness(
        _packet(expires_at="2026-05-18T00:30:00+00:00", valid_for_seconds=None),
        readiness_evidence_refs=["evidence://readiness/jarvis"],
        now_at="2026-05-18T00:30:01+00:00",
    )
    expired_by_ttl = verify_startup_packet_readiness(
        _packet(valid_for_seconds=60),
        readiness_evidence_refs=["evidence://readiness/jarvis"],
        now_at="2026-05-18T00:02:00+00:00",
    )
    no_freshness = verify_startup_packet_readiness(
        _packet(valid_for_seconds=None, expires_at=None),
        readiness_evidence_refs=["evidence://readiness/jarvis"],
        now_at="2026-05-18T00:02:00+00:00",
    )

    assert expired_by_expires_at.valid is False
    assert expired_by_ttl.valid is False
    assert no_freshness.valid is False
    assert "STARTUP_PACKET_EXPIRED" in expired_by_expires_at.errors
    assert "STARTUP_PACKET_EXPIRED" in expired_by_ttl.errors
    assert "STARTUP_PACKET_FRESHNESS_UNDECLARED" in no_freshness.errors
