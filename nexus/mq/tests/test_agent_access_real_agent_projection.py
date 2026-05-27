from nexus.mq.agent_access_read_model import build_agent_access_read_model


def test_agent_access_projection_exposes_lifecycle_refs_without_raw_mutation():
    model = build_agent_access_read_model(
        agents=[],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        candidate_runtime_projection=[
            {
                "projection_type": "real_agent_runtime",
                "agent_id": "jarvis",
                "runtime_instance_id": "jarvis-runtime-001",
                "lifecycle_state": "idle",
                "presence_state": "idle",
                "startup_packet_ref": "startup://jarvis/run-001",
                "readiness_evidence_ref": "evidence://jarvis/readiness",
                "active_decision_ids": ["decision-001"],
                "active_reservation_lease_ids": ["lease-001"],
                "assignment_timeout_seconds": 30,
                "raw_message": {"authorization": "bearer abc"},
                "credential": "secret",
            }
        ],
    )

    payload = model.to_dict()
    projection = payload["candidate_runtimes"][0]
    rendered = str(payload).lower()

    assert projection["lifecycle_state"] == "idle"
    assert projection["readiness_evidence_ref"] == "evidence://jarvis/readiness"
    assert projection["active_decision_ids"] == ["decision-001"]
    assert projection["active_reservation_lease_ids"] == ["lease-001"]
    assert projection["assignment_timeout_seconds"] == 30
    assert "raw_message" not in rendered
    assert "credential" not in rendered
