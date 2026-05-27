from nexus.mq.heartbeat_presence_controller import HeartbeatPresenceController, HeartbeatPresencePolicy


def test_heartbeat_presence_ttl_marks_stale_then_offline():
    controller = HeartbeatPresenceController(policy=HeartbeatPresencePolicy())
    controller.record_heartbeat(
        runtime_instance_id="jarvis-runtime-001",
        sequence=1,
        observed_at="2026-05-27T07:00:00+00:00",
        load_score=0.2,
        accepting_new_work=True,
    )

    fresh = controller.evaluate_presence(
        runtime_instance_id="jarvis-runtime-001",
        now_at="2026-05-27T07:00:59+00:00",
    )
    stale = controller.evaluate_presence(
        runtime_instance_id="jarvis-runtime-001",
        now_at="2026-05-27T07:01:01+00:00",
    )
    offline = controller.evaluate_presence(
        runtime_instance_id="jarvis-runtime-001",
        now_at="2026-05-27T07:04:01+00:00",
    )

    assert controller.policy.heartbeat_interval_seconds == 15
    assert controller.policy.heartbeat_ttl_seconds == 60
    assert fresh.presence_state == "idle"
    assert fresh.dispatch_fresh is True
    assert stale.presence_state == "stale"
    assert stale.dispatch_fresh is False
    assert "HEARTBEAT_STALE" in stale.errors
    assert offline.presence_state == "offline"
    assert "RUNTIME_OFFLINE_BY_TTL" in offline.errors


def test_heartbeat_presence_rejects_sequence_regression():
    controller = HeartbeatPresenceController(policy=HeartbeatPresencePolicy())
    first = controller.record_heartbeat(
        runtime_instance_id="jarvis-runtime-001",
        sequence=2,
        observed_at="2026-05-27T07:00:00+00:00",
    )
    second = controller.record_heartbeat(
        runtime_instance_id="jarvis-runtime-001",
        sequence=1,
        observed_at="2026-05-27T07:00:15+00:00",
    )

    assert first.accepted is True
    assert second.accepted is False
    assert "HEARTBEAT_SEQUENCE_REGRESSION" in second.errors
