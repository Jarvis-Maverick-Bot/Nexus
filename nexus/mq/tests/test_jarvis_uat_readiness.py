"""Jarvis UAT readiness proofs for Phase 3 runtime validation."""

from __future__ import annotations

import os

from nexus.mq.adapter_nats import MqAdapterNats
from nexus.mq.identity import AgentIdentityStore
from nexus.mq.listener_runtime import ListenerRuntime
from nexus.mq.protocol import build_protocol_envelope
from nexus.mq.protocol_boundary import ProtocolMessageBoundary
from nexus.mq.protocol_routing import build_agent_callback_subject, build_agent_inbox_subject


def _uat_identity_config_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "agents_uat.yaml")
    )


def _nova_to_jarvis_command():
    return build_protocol_envelope(
        message_type="command",
        source_agent_id="nova",
        source_runtime_instance_id="nova-uat-main-20260508",
        source_role="nova",
        authority_scope="workflow.command",
        payload={"command": "runtime_validation_probe"},
        target_agent_id="jarvis",
        reply_to_subject=build_agent_callback_subject("nova"),
        causation_id=None,
    )


def _jarvis_to_nova_result(request):
    return build_protocol_envelope(
        message_type="result",
        source_agent_id="jarvis",
        source_runtime_instance_id="jarvis-uat-main-20260508",
        source_role="jarvis",
        authority_scope="workflow.result",
        payload={"status": "accepted"},
        target_agent_id="nova",
        reply_to_subject=build_agent_callback_subject("nova"),
        correlation_id=request.correlation_id,
        causation_id=request.message_id,
        idempotency_key="result:jarvis:uat-proof",
    )


def test_uat_identity_config_matches_jarvis_nova_runtime_ids():
    store = AgentIdentityStore.from_yaml_file(_uat_identity_config_path())

    jarvis = store.get_agent("jarvis")
    nova = store.get_agent("nova")

    assert jarvis is not None
    assert nova is not None
    assert jarvis.runtime_instance_id == "jarvis-uat-main-20260508"
    assert nova.runtime_instance_id == "nova-uat-main-20260508"


def test_nats_adapter_routes_nova_command_to_jarvis_inbox_without_fallback():
    request = _nova_to_jarvis_command()

    # Exercise the real NATS adapter routing method without opening a broker connection.
    adapter = object.__new__(MqAdapterNats)
    subject = MqAdapterNats._resolve_subject(adapter, request.to_dict())

    assert subject == build_agent_inbox_subject("jarvis")


def test_listener_boundary_accepts_nova_command_on_jarvis_inbox():
    store = AgentIdentityStore.from_yaml_file(_uat_identity_config_path())
    boundary = ProtocolMessageBoundary(store)
    request = _nova_to_jarvis_command()
    subject = build_agent_inbox_subject("jarvis")

    outbound = boundary.validate_outbound(request.to_dict())
    inbound = boundary.validate_inbound_for_consumer(
        consumer_agent_id="jarvis",
        subject=subject,
        envelope_dict=request.to_dict(),
    )

    assert outbound.valid is True
    assert outbound.subject == subject
    assert inbound.valid is True


def test_nats_adapter_routes_jarvis_result_to_nova_callback_subject():
    request = _nova_to_jarvis_command()
    result = _jarvis_to_nova_result(request)

    adapter = object.__new__(MqAdapterNats)
    subject = MqAdapterNats._resolve_subject(adapter, result.to_dict())

    assert subject == build_agent_callback_subject("nova")


def test_listener_classifies_jarvis_inbox_and_nova_callback_subjects():
    assert ListenerRuntime._is_business_subject(build_agent_inbox_subject("jarvis")) is True
    assert ListenerRuntime._is_callback_subject(build_agent_callback_subject("nova")) is True

