from nexus.mq.heartbeat_policy import HeartbeatPolicy, validate_heartbeat_policy
from nexus.mq.heartbeat_runtime import HeartbeatPacket, validate_heartbeat_packet
from nexus.mq.tests.test_agent_registry_persistence import NOW, _record


def _packet(**overrides):
    data = {
        "agent_id": "jarvis",
        "runtime_instance_id": "jarvis-runtime-001",
        "registry_revision_seen": 1,
        "emitted_at": NOW,
        "heartbeat_sequence": 1,
        "desired_presence_state": "idle",
        "startup_packet_ref": "startup-packet://jarvis",
        "readiness_evidence_ref": "evidence://readiness/jarvis",
        "evidence_refs": ["evidence://heartbeat/jarvis/1"],
    }
    data.update(overrides)
    return HeartbeatPacket(**data)


def test_heartbeat_packet_requires_runtime_identity_match():
    result = validate_heartbeat_packet(
        _packet(runtime_instance_id="other-runtime"),
        current_record=_record(),
        current_revision=1,
        policy=HeartbeatPolicy(),
        now_at=NOW,
    )

    assert result.valid is False
    assert "RUNTIME_INSTANCE_MISMATCH" in result.errors


def test_heartbeat_sequence_must_be_monotonic():
    result = validate_heartbeat_packet(
        _packet(heartbeat_sequence=3),
        current_record=_record(),
        current_revision=1,
        previous_sequence=3,
        policy=HeartbeatPolicy(),
        now_at=NOW,
    )

    assert result.valid is False
    assert "STALE_HEARTBEAT_SEQUENCE" in result.errors


def test_heartbeat_clock_skew_is_rejected():
    result = validate_heartbeat_packet(
        _packet(emitted_at="2026-05-19T00:05:00+00:00"),
        current_record=_record(),
        current_revision=1,
        policy=HeartbeatPolicy(max_clock_skew_seconds=10),
        now_at=NOW,
    )

    assert result.valid is False
    assert "HEARTBEAT_CLOCK_SKEW_EXCEEDED" in result.errors


def test_heartbeat_rejects_secret_material_and_business_completion_claim():
    result = validate_heartbeat_packet(
        _packet(evidence_refs=["token=abc123"], not_business_completion=False),
        current_record=_record(),
        current_revision=1,
        policy=HeartbeatPolicy(),
        now_at=NOW,
    )

    assert result.valid is False
    assert "HEARTBEAT_CANNOT_BE_BUSINESS_COMPLETION" in result.errors
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_heartbeat_policy_blocks_daemon_mode_in_phase_b():
    result = validate_heartbeat_policy(HeartbeatPolicy(supervisor_mode="daemon"))

    assert result.valid is False
    assert "HEARTBEAT_DAEMON_MODE_NOT_AUTHORIZED" in result.errors
