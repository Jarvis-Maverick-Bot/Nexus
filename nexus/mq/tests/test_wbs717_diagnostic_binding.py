from nexus.mq.message_contracts import validate_agent_transport_envelope
from nexus.mq.payloads import CommandMessagePayload
from nexus.mq.protocol_routing import (
    build_agent_transport_subject,
    build_agent_transport_return_subject,
    validate_agent_transport_subject,
)
from nexus.mq.agent_transport_binding import (
    AGENT_TRANSPORT_DEFAULT_NO_GO_SCOPE,
    AgentTransportBinding,
    build_agent_transport_envelope,
    validate_agent_transport_binding,
)


def _binding() -> AgentTransportBinding:
    return AgentTransportBinding(
        run_id="wbs717-run-001",
        source_agent_id="thunder",
        source_runtime_instance_id="rt-thunder-001",
        source_role="implementer",
        target_agent_id="jarvis",
        target_runtime_instance_id="rt-jarvis-001",
        target_role="diagnostic_target",
        capability="live_mq_diagnostic",
        authority_scope="wbs_7_17_nova_cleared",
        binding_policy_ref="policy://wbs717/live-send-receive",
        subject=build_agent_transport_subject("wbs717-run-001", "jarvis"),
        reply_to_subject=build_agent_transport_return_subject("wbs717-run-001", "thunder"),
        payload_schema="nexus.mq.payloads.CommandMessagePayload",
        credential_ref="credential-resolution://wbs717/stub",
        no_go_scope=list(AGENT_TRANSPORT_DEFAULT_NO_GO_SCOPE),
    )


def test_wbs717_subject_validation_rejects_legacy_broad_routes():
    assert validate_agent_transport_subject("agent.jarvis.inbox", "wbs717-run-001").valid is False
    assert validate_agent_transport_subject("workflow.live_mq_diagnostic.requests", "wbs717-run-001").valid is False
    assert validate_agent_transport_subject("nexus.agent_transport.wbs717-run-001.jarvis.>", "wbs717-run-001").valid is False


def test_wbs717_binding_builds_strict_command_envelope():
    binding = _binding()
    assert validate_agent_transport_binding(binding) == []

    envelope = build_agent_transport_envelope(
        binding=binding,
        message_type="Command_Message",
        payload=CommandMessagePayload(
            command_name="wbs717_diagnostic_send_receive",
            target_handler="jarvis.diagnostic.intake",
            input_refs=["authority://wbs717/kickoff"],
            expected_outputs=["transport_evidence"],
            allowed_side_effects=[],
            completion_event_type="diagnostic_candidate_returned",
        ),
        payload_hash="sha256:payload",
        expires_at="2026-05-21T03:00:00Z",
        idempotency_key="idem-wbs717-001",
        correlation_id="corr-wbs717-001",
    )

    result = validate_agent_transport_envelope(envelope)

    assert result.valid is True
    assert envelope.target_runtime_instance_id == "rt-jarvis-001"
    assert envelope.no_go_scope == list(AGENT_TRANSPORT_DEFAULT_NO_GO_SCOPE)


def test_wbs717_binding_rejects_secret_material_references():
    binding = _binding()
    binding.credential_ref = "secret://literal-token"

    errors = validate_agent_transport_binding(binding)

    assert "AGENT_TRANSPORT_BINDING_MUST_REFERENCE_RESOLVER_OUTPUT_NOT_SECRET" in errors
