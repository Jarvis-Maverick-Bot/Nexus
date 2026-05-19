import pytest

from nexus.mq.agent_access_read_model import build_agent_access_read_model
from nexus.mq.tests.test_agent_registry_persistence import _record


def test_heartbeat_projection_is_read_only_and_redacted():
    model = build_agent_access_read_model(
        agents=[_record(presence_state="degraded", accepting_new_work=False)],
        assignments=[],
        outbox_items=[],
        adapter_health=[],
        exceptions=[],
        evidence=[],
        heartbeat_projection={
            "jarvis": {
                "agent_id": "jarvis",
                "supervisor_state": "degraded",
                "presence_state": "degraded",
                "heartbeat_sequence": 7,
                "heartbeat_evidence_ref": "evidence://heartbeat/jarvis/7",
                "health_summary_ref": "evidence://heartbeat/health",
                "projection_status": "degraded",
                "raw_private_payload": {"token": "abc"},
                "password": "abc",
            }
        },
    )

    payload = model.to_dict()
    rendered = str(payload).lower()

    assert payload["read_only"] is True
    assert payload["not_business_completion"] is True
    assert payload["presence"][0]["supervisor_state"] == "degraded"
    assert payload["presence"][0]["heartbeat_sequence"] == 7
    assert payload["presence"][0]["projection_status"] == "degraded"
    assert "raw_private_payload" not in rendered
    assert "password" not in rendered
    assert "token" not in rendered
    with pytest.raises(PermissionError):
        model.apply_operator_action("start_heartbeat_daemon")
