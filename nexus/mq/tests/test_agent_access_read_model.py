import pytest

from nexus.mq.agent_access_read_model import build_agent_access_read_model
from nexus.mq.channel_outbox import ChannelOutbox
from nexus.mq.tests.test_agent_registry_readiness import _record


def test_agent_access_read_model_separates_status_families_and_labels():
    outbox = ChannelOutbox()
    item = outbox.enqueue(
        correlation_id="corr-read-model",
        causation_id="msg-command",
        idempotency_key="send:read-model",
        target_channel="feishu",
        target_channel_instance_id="feishu-main",
        target_principal_id="principal:alex",
        target_channel_identity_ref="feishu:user:alex",
        channel_thread_ref="thread:4.19",
        content_ref="content://reply/read-model",
        delivery_policy={"privacy_scope": "project"},
    )
    model = build_agent_access_read_model(
        agents=[_record()],
        assignments=[],
        outbox_items=[item],
        adapter_health=[{"adapter_id": "feishu-main", "adapter_type": "feishu", "status": "healthy"}],
        exceptions=[{"event_type": "identity_unresolved", "severity": "warning", "owner": "operator"}],
        evidence=[{"evidence_ref": "evidence://agent-access/read-model"}],
    )

    payload = model.to_dict()

    assert payload["read_only"] is True
    assert payload["status_families"]["ack"] == "durable_intake_only"
    assert payload["status_families"]["delivery"] == "visible_delivery_only"
    assert payload["agent_roster"][0]["agent_id"] == "jarvis"
    assert payload["outbox"][0]["status"] == "queued"
    with pytest.raises(PermissionError):
        model.apply_operator_action("assign_work")
