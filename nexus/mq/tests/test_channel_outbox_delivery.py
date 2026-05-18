from nexus.mq.channel_outbox import ChannelOutbox, visible_delivery_evidence


def test_channel_outbox_separates_provider_ack_sent_delivered_from_completion():
    outbox = ChannelOutbox()
    item = outbox.enqueue(
        correlation_id="corr-outbox",
        causation_id="msg-command",
        idempotency_key="send:msg-command",
        target_channel="feishu",
        target_channel_instance_id="feishu-main",
        target_principal_id="principal:alex",
        target_channel_identity_ref="feishu:user:alex",
        channel_thread_ref="thread:4.19",
        content_ref="content://reply/001",
        delivery_policy={"privacy_scope": "project"},
    )

    outbox.transition(item.outbox_id, "sending")
    outbox.transition(item.outbox_id, "provider_acknowledged", channel_message_ref="feishu-msg-001")
    delivered = outbox.transition(item.outbox_id, "delivered")
    evidence = visible_delivery_evidence(delivered)

    assert delivered.status == "delivered"
    assert evidence["visible_delivery_only"] is True
    assert evidence["not_business_completion"] is True
    assert delivered.not_business_completion is True


def test_channel_outbox_suppresses_duplicate_visible_send():
    outbox = ChannelOutbox()
    first = outbox.enqueue(
        correlation_id="corr-outbox",
        causation_id="msg-command",
        idempotency_key="send:msg-command",
        target_channel="telegram",
        target_channel_instance_id="telegram-main",
        target_principal_id="principal:alex",
        target_channel_identity_ref="telegram:user:alex",
        channel_thread_ref="thread:4.19",
        content_ref="content://reply/001",
        delivery_policy={"privacy_scope": "project"},
    )
    duplicate = outbox.enqueue(
        correlation_id="corr-outbox",
        causation_id="msg-command",
        idempotency_key="send:msg-command",
        target_channel="telegram",
        target_channel_instance_id="telegram-main",
        target_principal_id="principal:alex",
        target_channel_identity_ref="telegram:user:alex",
        channel_thread_ref="thread:4.19",
        content_ref="content://reply/001",
        delivery_policy={"privacy_scope": "project"},
    )

    assert first.status == "queued"
    assert duplicate.status == "duplicate_suppressed"
    assert duplicate.last_error_ref == f"duplicate_of:{first.outbox_id}"
