from nexus.mq.adapter import MqAdapterStub
from nexus.mq.agent_message_capability_policy import (
    AgentMessageCapabilityRequest,
    evaluate_agent_message_capability,
)
from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.live_send_receive import (
    CredentialResolutionResult,
    RunScopedDedupeLedger,
    publish_live_message,
    publish_return_message,
    receive_live_message_once,
)
from nexus.mq.live_transport_evidence import evaluate_live_mq_evidence_gate, evidence_record
from nexus.mq.payloads import CommandMessagePayload, ResultMessagePayload
from nexus.mq.protocol_routing import build_agent_transport_subject, build_agent_transport_return_subject
from nexus.mq.agent_transport_binding import (
    AgentTransportBinding,
    build_agent_transport_envelope,
)


RUN_ID = "wbs717-run-001"
NOW = "2026-05-21T02:00:00Z"
EXPIRES = "2026-05-21T03:00:00Z"
WBS717_NO_GO_SCOPE = [
    "runtime_listener_daemon_start",
    "assignment_publish",
    "private_agent_invocation",
    "business_execution",
    "broker_config_mutation",
    "wbs_7_17_pass",
    "wbs_7_18",
]


def _target_record() -> AgentRegistryRecord:
    return AgentRegistryRecord(
        agent_id="jarvis",
        runtime_instance_id="rt-jarvis-001",
        role="diagnostic_target",
        owner_principal_id="jarvis-owner",
        runtime_type="test_stub",
        channel_bindings=[build_agent_transport_subject(RUN_ID, "jarvis")],
        capabilities=["live_mq_diagnostic"],
        authority_scopes=["wbs_7_17_nova_cleared"],
        allowed_task_boundaries=["agent_transport_diagnostic_only"],
        initialization_status="ready",
        registry_status="active",
        presence_state="idle",
        heartbeat_ttl_seconds=300,
        last_heartbeat_at=NOW,
        current_assignment_refs=[],
        protocol_versions_supported=["1.0"],
        trust_material_ref="trust://jarvis",
        startup_packet_ref="startup://jarvis/001",
        readiness_evidence_ref="evidence://jarvis/ready",
        startup_packet_expires_at=EXPIRES,
        created_at=NOW,
        updated_at=NOW,
    )


def _binding(source: str = "thunder", target: str = "jarvis") -> AgentTransportBinding:
    return AgentTransportBinding(
        run_id=RUN_ID,
        source_agent_id=source,
        source_runtime_instance_id=f"rt-{source}-001",
        source_role="implementer" if source == "thunder" else "diagnostic_target",
        target_agent_id=target,
        target_runtime_instance_id=f"rt-{target}-001",
        target_role="diagnostic_target" if target == "jarvis" else "implementer",
        capability="live_mq_diagnostic",
        authority_scope="wbs_7_17_nova_cleared",
        binding_policy_ref="policy://wbs717/live-send-receive",
        subject=build_agent_transport_subject(RUN_ID, target),
        reply_to_subject=build_agent_transport_return_subject(RUN_ID, source),
        payload_schema="nexus.mq.payloads.CommandMessagePayload",
        credential_ref="credential-resolution://wbs717/stub",
        no_go_scope=list(WBS717_NO_GO_SCOPE),
    )


def _policy(subject: str):
    request = AgentMessageCapabilityRequest(
        source_agent_id="thunder",
        source_runtime_instance_id="rt-thunder-001",
        target_agent_id="jarvis",
        target_runtime_instance_id="rt-jarvis-001",
        capability="live_mq_diagnostic",
        authority_scope="wbs_7_17_nova_cleared",
        binding_policy_ref="policy://wbs717/live-send-receive",
        subject=subject,
        payload_schema="nexus.mq.payloads.CommandMessagePayload",
        allowed_task_boundary="agent_transport_diagnostic_only",
    )
    return evaluate_agent_message_capability(request, target_record=_target_record(), now_at=NOW)


def test_live_send_receive_ack_and_duplicate_are_transport_only():
    adapter = MqAdapterStub()
    binding = _binding()
    policy = _policy(binding.subject)
    credential = CredentialResolutionResult(
        accepted=True,
        credential_ref="credential-resolution://wbs717/stub",
        resolver_ref="resolver://wbs717/no-secret",
    )
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
        expires_at=EXPIRES,
        idempotency_key="idem-wbs717-001",
        correlation_id="corr-wbs717-001",
    )

    send = publish_live_message(
        adapter,
        envelope,
        subject=binding.subject,
        policy_decision=policy,
        credential_result=credential,
    )
    receive = receive_live_message_once(
        adapter,
        expected_subject=binding.subject,
        expected_target_agent_id="jarvis",
        expected_target_runtime_instance_id="rt-jarvis-001",
        policy_decision=policy,
        dedupe_ledger=RunScopedDedupeLedger(),
        safe_intake=lambda msg: {"intake_ref": f"intake://{msg['message_id']}"},
    )

    adapter.publish({**envelope.to_dict(), "subject": binding.subject})
    duplicate = receive_live_message_once(
        adapter,
        expected_subject=binding.subject,
        expected_target_agent_id="jarvis",
        expected_target_runtime_instance_id="rt-jarvis-001",
        policy_decision=policy,
        dedupe_ledger=RunScopedDedupeLedger(
            claims={envelope.idempotency_key: (str(envelope.payload_hash), envelope.message_id)}
        ),
        safe_intake=lambda msg: {"unexpected": msg["message_id"]},
    )

    assert send.published is True
    assert send.ack and send.ack["ack_level"] == "broker_received"
    assert receive.acked is True
    assert receive.side_effects_allowed is True
    assert duplicate.duplicate is True
    assert duplicate.side_effects_allowed is False
    assert all(record.not_business_completion is True for record in send.evidence + receive.evidence + duplicate.evidence)


def test_live_send_fails_closed_without_policy_or_credential():
    adapter = MqAdapterStub()
    binding = _binding()
    denied_policy = _policy(binding.subject)
    denied_policy.allowed = False
    denied_policy.errors = ["AGENT_MESSAGE_POLICY_DENIED"]
    envelope = build_agent_transport_envelope(
        binding=binding,
        message_type="Command_Message",
        payload=CommandMessagePayload(
            command_name="wbs717_diagnostic_send_receive",
            target_handler="jarvis.diagnostic.intake",
            completion_event_type="diagnostic_candidate_returned",
        ),
        payload_hash="sha256:payload",
        expires_at=EXPIRES,
        idempotency_key="idem-wbs717-002",
        correlation_id="corr-wbs717-002",
    )

    result = publish_live_message(
        adapter,
        envelope,
        subject=binding.subject,
        policy_decision=denied_policy,
        credential_result=CredentialResolutionResult(
            accepted=False,
            credential_ref="",
            errors=["CREDENTIAL_RESOLUTION_REJECTED"],
        ),
    )

    assert result.accepted is False
    assert result.published is False
    assert "AGENT_MESSAGE_POLICY_DENIED" in result.errors
    assert "CREDENTIAL_RESOLUTION_REJECTED" in result.errors
    assert adapter.consume() is None


def test_live_send_rejects_broad_reply_to_subject_before_publish():
    adapter = MqAdapterStub()
    binding = _binding()
    binding.reply_to_subject = "agent.thunder.callbacks"
    policy = _policy(binding.subject)
    envelope = build_agent_transport_envelope(
        binding=binding,
        message_type="Command_Message",
        payload=CommandMessagePayload(
            command_name="wbs717_diagnostic_send_receive",
            target_handler="jarvis.diagnostic.intake",
            completion_event_type="diagnostic_candidate_returned",
        ),
        payload_hash="sha256:payload",
        expires_at=EXPIRES,
        idempotency_key="idem-wbs717-reply-001",
        correlation_id="corr-wbs717-reply-001",
    )

    result = publish_live_message(
        adapter,
        envelope,
        subject=binding.subject,
        policy_decision=policy,
        credential_result=CredentialResolutionResult(
            accepted=True,
            credential_ref="credential-resolution://wbs717/stub",
        ),
    )

    assert result.accepted is False
    assert result.published is False
    assert "reply_to_subject: AGENT_TRANSPORT_SUBJECT_OUT_OF_SCOPE: agent.thunder.callbacks" in result.errors
    assert adapter.consume() is None


def test_result_return_routes_to_reply_subject_and_gate_shape_is_not_pass():
    adapter = MqAdapterStub()
    binding = _binding()
    policy = _policy(binding.subject)
    credential = CredentialResolutionResult(
        accepted=True,
        credential_ref="credential-resolution://wbs717/stub",
    )
    result_envelope = build_agent_transport_envelope(
        binding=binding,
        message_type="Result_Message",
        payload=ResultMessagePayload(
            result_id="res-001",
            original_message_id="msg-001",
            original_idempotency_key="idem-wbs717-001",
            result_status="accepted_candidate",
            completed_at=NOW,
            evidence_refs=["evidence://wbs717/receive"],
        ),
        payload_hash="sha256:result",
        expires_at=EXPIRES,
        idempotency_key="idem-wbs717-result-001",
        correlation_id="corr-wbs717-001",
        causation_id="msg-001",
    )

    returned = publish_return_message(
        adapter,
        result_envelope,
        policy_decision=policy,
        credential_result=credential,
    )
    gate = evaluate_live_mq_evidence_gate(
        [
            evidence_record("publish", message_id="msg-001", subject=binding.subject, status="broker_received"),
            evidence_record("receive", message_id="msg-001", subject=binding.subject, status="accepted"),
            evidence_record("ack", message_id="msg-001", subject=binding.subject, status="consumer_intake"),
            *returned.evidence,
            evidence_record("duplicate", message_id="msg-001", subject=binding.subject, status="suppressed"),
            evidence_record("timeout_or_anomaly", message_id="msg-001", subject=build_agent_transport_subject(RUN_ID, "ops", "timeout"), status="not_observed"),
            evidence_record("cleanup", message_id="msg-001", subject=binding.subject, status="not_started_runtime"),
            evidence_record("secret_scan", message_id="msg-001", subject=binding.subject, status="clean"),
        ]
    )

    assert returned.published is True
    assert adapter.consume()["subject"] == binding.reply_to_subject
    assert gate.accepted is True
    assert gate.not_pass is True
