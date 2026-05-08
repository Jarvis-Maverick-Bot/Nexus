"""V0.3 message-family registry for Nexus MQ/HITL skeleton contracts."""

from __future__ import annotations

from dataclasses import dataclass

from nexus.mq.taxonomy import (
    ALL_MESSAGE_TYPES,
    DEFERRED_MESSAGE_TYPES,
    MESSAGE_CLASSES_BY_TYPE,
    PRIMARY_MESSAGE_TYPES,
)


@dataclass(frozen=True)
class MessageFamilyDefinition:
    message_type: str
    message_class: str
    skeleton_status: str
    transport_active: bool


MESSAGE_FAMILY_DEFINITIONS = tuple(
    MessageFamilyDefinition(
        message_type=message_type,
        message_class=MESSAGE_CLASSES_BY_TYPE[message_type],
        skeleton_status="primary" if message_type in PRIMARY_MESSAGE_TYPES else "deferred",
        transport_active=message_type not in DEFERRED_MESSAGE_TYPES,
    )
    for message_type in ALL_MESSAGE_TYPES
)

MESSAGE_FAMILY_BY_TYPE = {
    definition.message_type: definition for definition in MESSAGE_FAMILY_DEFINITIONS
}


def get_message_family(message_type: str) -> MessageFamilyDefinition | None:
    return MESSAGE_FAMILY_BY_TYPE.get(message_type)


def primary_message_families() -> list[MessageFamilyDefinition]:
    return [definition for definition in MESSAGE_FAMILY_DEFINITIONS if definition.skeleton_status == "primary"]


def deferred_message_families() -> list[MessageFamilyDefinition]:
    return [definition for definition in MESSAGE_FAMILY_DEFINITIONS if definition.skeleton_status == "deferred"]
