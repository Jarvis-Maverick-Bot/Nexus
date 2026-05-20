"""Contract-first V0.3 taxonomy and payload validation tests."""

from nexus.mq.message_contracts import (
    build_execution_envelope,
    is_transport_active,
    validate_execution_message,
    validate_wbs717_diagnostic_envelope,
)
from nexus.mq.message_families import (
    MESSAGE_FAMILY_DEFINITIONS,
    deferred_message_families,
    get_message_family,
    primary_message_families,
)
from nexus.mq.payloads import AbnormalStateRecord, ResultMessagePayload
from nexus.mq.taxonomy import (
    ABNORMAL_CLASSES,
    DEFERRED_MESSAGE_TYPES,
    PRIMARY_MESSAGE_TYPES,
    RETRY_POLICY_CLASSIFICATIONS,
)


def test_v03_message_family_taxonomy_is_exact():
    primary = primary_message_families()
    deferred = deferred_message_families()

    assert len(primary) == 11
    assert len(deferred) == 2
    assert [family.message_type for family in primary] == list(PRIMARY_MESSAGE_TYPES)
    assert [family.message_type for family in deferred] == list(DEFERRED_MESSAGE_TYPES)
    assert len(MESSAGE_FAMILY_DEFINITIONS) == 13


def test_retry_message_is_independent_primary_family():
    retry_family = get_message_family("Retry_Message")

    assert retry_family is not None
    assert retry_family.skeleton_status == "primary"
    assert retry_family.message_class == "retry"
    assert retry_family.transport_active is True


def test_wbs717_result_message_payload_is_primary_transport_family():
    result_family = get_message_family("Result_Message")

    assert result_family is not None
    assert result_family.skeleton_status == "primary"
    assert result_family.message_class == "result"
    assert result_family.transport_active is True

    payload = ResultMessagePayload(
        result_id="res-001",
        original_message_id="msg-001",
        original_idempotency_key="idem-001",
        result_status="accepted_candidate",
        completed_at="2026-05-21T02:00:00Z",
        evidence_refs=["evidence://wbs717/receive"],
    )
    assert payload.validate().valid is True


def test_deferred_message_families_validate_but_transport_is_inactive():
    evidence = build_execution_envelope(
        message_type="Evidence_Write_Message",
        workflow_instance_id="wf-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="codex",
        payload={
            "evidence_write_id": "ew-001",
            "workflow_instance_id": "wf-001",
            "transition_id": "tr-001",
            "evidence_ref": "evidence://pkg/1",
            "artifact_ref": "artifact://build/1",
            "payload_hash": "abc123",
            "written_by": "codex",
            "written_at": "2026-05-08T12:00:00Z",
            "commit_phase": "pending",
        },
    )
    transition = build_execution_envelope(
        message_type="State_Transition_Message",
        workflow_instance_id="wf-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="codex",
        payload={
            "state_transition_id": "st-001",
            "workflow_instance_id": "wf-001",
            "transition_id": "tr-001",
            "previous_state": "in_review",
            "requested_state": "approved",
            "validation_result": "accepted",
            "written_by": "codex",
            "written_at": "2026-05-08T12:00:00Z",
            "commit_phase": "pending",
        },
    )

    evidence_result = validate_execution_message(evidence)
    transition_result = validate_execution_message(transition)

    assert evidence_result.valid is True
    assert transition_result.valid is True
    assert is_transport_active("Evidence_Write_Message") is False
    assert is_transport_active("State_Transition_Message") is False


def test_envelope_validates_payload_schema_for_correct_family():
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="codex",
        payload={
            "command_name": "dispatch_review",
            "target_handler": "review.dispatch",
            "input_refs": ["artifact://build/1"],
            "expected_outputs": ["review_task"],
            "allowed_side_effects": ["publish_review_task"],
            "commit_pattern": "local_transactional_default",
            "completion_event_type": "review_dispatched",
        },
    )

    result = validate_execution_message(envelope)

    assert result.valid is True
    assert result.family is not None
    assert result.family.message_type == "Command_Message"


def test_envelope_rejects_payload_schema_mismatch():
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wf-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="codex",
        payload={
            "feedback_id": "fb-001",
            "review_task_id": "rt-001",
            "authority_wait_id": "wait-001",
            "reviewer_actor_id": "alex",
            "reviewer_role": "reviewer",
            "action": "Approve",
            "submitted_at": "2026-05-08T12:00:00Z",
        },
    )

    result = validate_execution_message(envelope)

    assert result.valid is False
    assert "PAYLOAD_SCHEMA_MISMATCH: Command_Message" in result.errors


def test_runtime_overlay_validation_can_be_required_separately():
    envelope = build_execution_envelope(
        message_type="Review_Task",
        workflow_instance_id="wf-001",
        workflow_type="delivery",
        workflow_version="1.0",
        producer="codex",
        payload={
            "review_task_id": "rt-001",
            "authority_wait_id": "wait-001",
            "review_target_ref": "artifact://build/1",
            "review_type": "gate_review",
            "allowed_actions": ["Approve", "Reject", "Revise"],
            "required_context_refs": ["ctx://1"],
            "display_summary": "Need review",
        },
    )

    result = validate_execution_message(envelope, require_runtime_overlay=True)

    assert result.valid is False
    assert "MISSING_RUNTIME_OVERLAY_FIELD: source_agent_id" in result.errors
    assert "MISSING_RUNTIME_OVERLAY_FIELD: authority_scope" in result.errors
    assert "MISSING_RUNTIME_OVERLAY_FIELD: target_agent_id" in result.errors


def test_wbs717_diagnostic_envelope_requires_strict_binding_overlay():
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id="wbs717-run-001",
        workflow_type="wbs_7_17_live_mq_diagnostic",
        workflow_version="7.17",
        producer="thunder",
        payload={
            "command_name": "wbs717_diagnostic_send_receive",
            "target_handler": "jarvis.diagnostic.intake",
            "input_refs": ["authority://wbs717/kickoff"],
            "expected_outputs": ["transport_evidence"],
            "allowed_side_effects": [],
            "commit_pattern": "local_transactional_default",
            "completion_event_type": "diagnostic_candidate_returned",
        },
        source_agent_id="thunder",
        source_runtime_instance_id="rt-thunder-001",
        source_role="implementer",
        target_agent_id="jarvis",
        target_runtime_instance_id="rt-jarvis-001",
        target_role="diagnostic_target",
        authority_scope="wbs_7_17_nova_cleared",
        capability="live_mq_diagnostic",
        binding_policy_ref="policy://wbs717/live-send-receive",
        reply_to_subject="nexus.wbs7_17.wbs717-run-001.thunder.callbacks",
        payload_schema="nexus.mq.payloads.CommandMessagePayload",
        payload_hash="sha256:abc",
        expires_at="2026-05-21T03:00:00Z",
        no_go_scope=[
            "runtime_listener_daemon_start",
            "assignment_publish",
            "private_agent_invocation",
            "business_execution",
            "broker_config_mutation",
            "wbs_7_17_pass",
            "wbs_7_18",
        ],
    )

    result = validate_wbs717_diagnostic_envelope(envelope)

    assert result.valid is True


def test_abnormal_class_taxonomy_is_exact():
    assert ABNORMAL_CLASSES == (
        "mechanism_stall",
        "business_stall",
        "owner_execution_stall",
        "durable_evidence_inconsistency",
        "duplicate_runtime_suspicion",
        "boundary_drift",
        "blocker_fade_out",
        "authority_stall",
        "notification_failure",
        "other",
    )
    assert len(ABNORMAL_CLASSES) == 10


def test_retry_policy_classifications_are_not_legal_abnormal_classes():
    for classification in RETRY_POLICY_CLASSIFICATIONS:
        record = AbnormalStateRecord(
            abnormal_state_id="abn-001",
            error_event_id="err-001",
            error_class="transport",
            abnormal_class=classification,
            detected_at="2026-05-08T12:00:00Z",
        )
        result = record.validate()
        assert result.valid is False
        assert any("INVALID_ABNORMAL_CLASS" in error for error in result.errors)
