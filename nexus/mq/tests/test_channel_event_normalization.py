from nexus.mq.channel_event import normalize_channel_event


def test_channel_event_normalizes_same_intent_across_channels():
    telegram = normalize_channel_event(
        {
            "source_channel": "telegram",
            "event_id": "tg-001",
            "actor_channel_identity_ref": "telegram:user:alex",
            "resolved_principal_id": "principal:alex",
            "permission_scope_ref": "project:nexus",
            "privacy_scope": "project",
            "text": "approve kickoff",
            "channel_thread_ref": "thread:4.19",
        }
    )
    feishu = normalize_channel_event(
        {
            "channel": "feishu",
            "message_id": "fs-001",
            "sender_id": "feishu:user:alex",
            "resolved_principal_id": "principal:alex",
            "permission_scope": "project:nexus",
            "privacy_scope": "project",
            "normalized_text_ref": "doc://normalized/approve-kickoff",
            "thread_id": "thread:4.19",
        }
    )

    assert telegram.valid is True
    assert feishu.valid is True
    assert telegram.event.resolved_principal_id == feishu.event.resolved_principal_id
    assert telegram.event.permission_scope_ref == feishu.event.permission_scope_ref
    assert telegram.event.privacy_scope == feishu.event.privacy_scope
    assert telegram.event.not_business_completion is True


def test_channel_event_rejects_missing_identity_and_privacy():
    result = normalize_channel_event({"source_channel": "unknown", "event_id": "evt-001", "text": "hello"})

    assert result.valid is False
    assert "UNKNOWN_CHANNEL" in result.errors
    assert "MISSING_ACTOR_IDENTITY" in result.errors
    assert "UNSUPPORTED_PRIVACY_SCOPE" in result.errors
