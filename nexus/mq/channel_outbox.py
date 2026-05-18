"""Channel outbox and visible-delivery dedupe for 4.19."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


OUTBOX_STATUSES = {
    "queued",
    "sending",
    "provider_acknowledged",
    "sent",
    "delivered",
    "failed_retryable",
    "failed_final",
    "uncertain",
    "duplicate_suppressed",
    "compensated",
}


@dataclass
class ChannelOutboxItem:
    outbox_id: str
    correlation_id: str
    causation_id: Optional[str]
    idempotency_key: str
    target_channel: str
    target_channel_instance_id: str
    target_principal_id: str
    target_channel_identity_ref: str
    channel_thread_ref: str
    content_ref: str
    delivery_policy: dict[str, Any]
    status: str
    attempt_count: int
    channel_message_ref: Optional[str]
    last_error_ref: Optional[str]
    created_at: str
    updated_at: str
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChannelOutbox:
    def __init__(self):
        self._items: dict[str, ChannelOutboxItem] = {}
        self._dedupe_index: dict[str, str] = {}

    def enqueue(
        self,
        *,
        correlation_id: str,
        causation_id: Optional[str],
        idempotency_key: str,
        target_channel: str,
        target_channel_instance_id: str,
        target_principal_id: str,
        target_channel_identity_ref: str,
        channel_thread_ref: str,
        content_ref: str,
        delivery_policy: dict[str, Any],
        created_at: Optional[str] = None,
    ) -> ChannelOutboxItem:
        dedupe_key = _dedupe_key(idempotency_key, target_channel, target_channel_identity_ref, content_ref)
        existing_id = self._dedupe_index.get(dedupe_key)
        if existing_id:
            existing = self._items[existing_id]
            duplicate = _copy_item(existing)
            duplicate.outbox_id = f"outbox-{uuid.uuid4().hex[:12]}"
            duplicate.status = "duplicate_suppressed"
            duplicate.updated_at = _now()
            duplicate.last_error_ref = f"duplicate_of:{existing.outbox_id}"
            self._items[duplicate.outbox_id] = duplicate
            return duplicate
        now_at = created_at or _now()
        item = ChannelOutboxItem(
            outbox_id=f"outbox-{uuid.uuid4().hex[:12]}",
            correlation_id=correlation_id,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
            target_channel=target_channel,
            target_channel_instance_id=target_channel_instance_id,
            target_principal_id=target_principal_id,
            target_channel_identity_ref=target_channel_identity_ref,
            channel_thread_ref=channel_thread_ref,
            content_ref=content_ref,
            delivery_policy=dict(delivery_policy),
            status="queued",
            attempt_count=0,
            channel_message_ref=None,
            last_error_ref=None,
            created_at=now_at,
            updated_at=now_at,
        )
        self._items[item.outbox_id] = item
        self._dedupe_index[dedupe_key] = item.outbox_id
        return item

    def transition(
        self,
        outbox_id: str,
        status: str,
        *,
        channel_message_ref: Optional[str] = None,
        last_error_ref: Optional[str] = None,
    ) -> ChannelOutboxItem:
        if status not in OUTBOX_STATUSES:
            raise ValueError(f"INVALID_OUTBOX_STATUS: {status}")
        item = self._items[outbox_id]
        item.status = status
        item.updated_at = _now()
        if status in {"sending", "failed_retryable"}:
            item.attempt_count += 1
        if channel_message_ref:
            item.channel_message_ref = channel_message_ref
        if last_error_ref:
            item.last_error_ref = last_error_ref
        return item

    def get(self, outbox_id: str) -> Optional[ChannelOutboxItem]:
        return self._items.get(outbox_id)

    def list_items(self) -> list[ChannelOutboxItem]:
        return list(self._items.values())


def visible_delivery_evidence(item: ChannelOutboxItem) -> dict[str, Any]:
    return {
        "outbox_id": item.outbox_id,
        "status": item.status,
        "channel_message_ref": item.channel_message_ref,
        "visible_delivery_only": True,
        "not_business_completion": True,
    }


def _dedupe_key(idempotency_key: str, target_channel: str, identity_ref: str, content_ref: str) -> str:
    return "|".join([idempotency_key, target_channel, identity_ref, content_ref])


def _copy_item(item: ChannelOutboxItem) -> ChannelOutboxItem:
    return ChannelOutboxItem(**item.to_dict())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
