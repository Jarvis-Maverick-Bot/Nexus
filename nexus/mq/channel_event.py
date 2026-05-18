"""Canonical channel event normalization for 4.19 Agent Access.

Channel events are adapter-facing evidence records. They do not mutate
governed workflow state and they do not imply business progress.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


SUPPORTED_CHANNELS = {"telegram", "feishu", "discord", "email"}
SUPPORTED_PRIVACY_SCOPES = {"public", "team", "project", "private", "restricted"}


@dataclass
class CanonicalChannelEvent:
    protocol_version: str
    event_id: str
    correlation_id: str
    causation_id: Optional[str]
    source_channel: str
    source_channel_instance_id: str
    channel_thread_ref: str
    channel_message_ref: str
    actor_channel_identity_ref: str
    resolved_principal_id: Optional[str]
    permission_scope_ref: str
    event_type: str
    content_refs: list[str]
    normalized_text_ref: str
    privacy_scope: str
    received_at: str
    expires_at: Optional[str]
    raw_event_ref: Optional[str] = None
    unresolved_identity: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChannelEventNormalizationResult:
    valid: bool
    event: Optional[CanonicalChannelEvent] = None
    errors: list[str] = field(default_factory=list)


def normalize_channel_event(raw_event: Mapping[str, Any]) -> ChannelEventNormalizationResult:
    """Normalize a provider event into a channel-neutral evidence record."""
    if not isinstance(raw_event, Mapping):
        return ChannelEventNormalizationResult(valid=False, errors=["UNNORMALIZABLE_PAYLOAD"])

    source_channel = _string(raw_event, "source_channel", "channel", "channel_type").lower()
    event_id = _string(raw_event, "event_id", "message_id", "id")
    actor_ref = _string(raw_event, "actor_channel_identity_ref", "actor_id", "sender_id", "from")
    privacy_scope = _string(raw_event, "privacy_scope")
    normalized_text_ref = _normalized_text_ref(raw_event, event_id)
    content_refs = _content_refs(raw_event, normalized_text_ref)

    errors: list[str] = []
    if source_channel not in SUPPORTED_CHANNELS:
        errors.append("UNKNOWN_CHANNEL")
    if not event_id:
        errors.append("MISSING_EVENT_ID")
    if not actor_ref:
        errors.append("MISSING_ACTOR_IDENTITY")
    if not normalized_text_ref and not content_refs:
        errors.append("UNNORMALIZABLE_PAYLOAD")
    if privacy_scope not in SUPPORTED_PRIVACY_SCOPES:
        errors.append("UNSUPPORTED_PRIVACY_SCOPE")
    if errors:
        return ChannelEventNormalizationResult(valid=False, errors=_dedupe(errors))

    event = CanonicalChannelEvent(
        protocol_version=str(raw_event.get("protocol_version") or "4.19.channel_event.v1"),
        event_id=event_id,
        correlation_id=_string(raw_event, "correlation_id") or f"corr-{event_id}",
        causation_id=_optional_string(raw_event, "causation_id"),
        source_channel=source_channel,
        source_channel_instance_id=_string(raw_event, "source_channel_instance_id", "channel_instance_id") or source_channel,
        channel_thread_ref=_string(raw_event, "channel_thread_ref", "thread_id") or f"{source_channel}:thread:default",
        channel_message_ref=_string(raw_event, "channel_message_ref", "message_ref") or f"{source_channel}:message:{event_id}",
        actor_channel_identity_ref=actor_ref,
        resolved_principal_id=_optional_string(raw_event, "resolved_principal_id"),
        permission_scope_ref=_string(raw_event, "permission_scope_ref", "permission_scope") or "unresolved",
        event_type=_string(raw_event, "event_type") or "message.created",
        content_refs=content_refs,
        normalized_text_ref=normalized_text_ref,
        privacy_scope=privacy_scope,
        received_at=_string(raw_event, "received_at") or datetime.now(timezone.utc).isoformat(),
        expires_at=_optional_string(raw_event, "expires_at"),
        raw_event_ref=_optional_string(raw_event, "raw_event_ref"),
        unresolved_identity=not bool(_optional_string(raw_event, "resolved_principal_id")),
    )
    return ChannelEventNormalizationResult(valid=True, event=event)


def _string(raw: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _optional_string(raw: Mapping[str, Any], *keys: str) -> Optional[str]:
    value = _string(raw, *keys)
    return value or None


def _normalized_text_ref(raw: Mapping[str, Any], event_id: str) -> str:
    value = _string(raw, "normalized_text_ref", "text_ref")
    if value:
        return value
    text = _string(raw, "normalized_text", "text")
    if text and event_id:
        return f"inline://normalized-channel-text/{event_id}"
    content = raw.get("content")
    if isinstance(content, Mapping) and isinstance(content.get("text"), str) and event_id:
        return f"inline://normalized-channel-text/{event_id}"
    return ""


def _content_refs(raw: Mapping[str, Any], normalized_text_ref: str) -> list[str]:
    refs = raw.get("content_refs")
    if isinstance(refs, list):
        return [str(ref) for ref in refs if str(ref).strip()]
    ref = _string(raw, "content_ref")
    if ref:
        return [ref]
    return [normalized_text_ref] if normalized_text_ref else []


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
