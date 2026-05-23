from nexus.mq.structured_task_models import (
    OwnerHandoffPacket,
    TaskEnvelope,
    TaskUnit,
    WorkspaceInitializationContextPlaceholder,
    WorkflowConstraintSet,
)
from nexus.mq.structured_task_validation import (
    validate_owner_handoff_packet,
    validate_task_envelope,
    validate_task_unit,
    validate_workspace_placeholder,
    validate_workflow_constraints,
)


def _constraints(**overrides):
    data = dict(
        constraint_id="constraint-001",
        source_refs=["wbs://7.19.1"],
        wbs_refs=["7.19.7"],
        gate_state="open",
        dependency_state="satisfied",
        dod=["done means evidence"],
        no_go_scope=["no runtime start"],
        evidence_requirements=["test log"],
        review_authority_refs=["nova"],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
    )
    data.update(overrides)
    return WorkflowConstraintSet(**data)


def _unit(**overrides):
    data = dict(
        task_id="task-001",
        parent_id=None,
        title="Task",
        objective="Objective",
        source_refs=["wbs://7.19.2"],
        source_hash="sha256:source",
        owner="thunder",
        verifier="nova",
        dependencies=[],
        priority="normal",
        status="draft",
        dod=["tests pass"],
        no_go_scope=["no live dispatch"],
        allowed_tools=["pytest"],
        allowed_write_surfaces=["nexus/mq/structured_task_*.py"],
        evidence_requirements=["log"],
        stop_conditions=["blocked"],
        escalation_conditions=["review"],
    )
    data.update(overrides)
    return TaskUnit(**data)


def test_missing_source_authority_fails_closed():
    result = validate_workflow_constraints(_constraints(source_refs=[]))

    assert result.ok is False
    assert "MISSING_SOURCE_REFS" in result.errors


def test_unapproved_workspace_initialization_change_blocks():
    placeholder = WorkspaceInitializationContextPlaceholder(
        workspace_context_id="workspace-001",
        workspace_refs=["workspace://nexus"],
        project_initialization_refs=["project://init"],
        active_wbs_ref="7.19",
        source_hash="sha256:source",
        policy_hash="sha256:policy",
        known_fields={"repo": "Nexus"},
        tbd_fields=["stage00_schema"],
        last_human_approved_change_ref="",
        placeholder_status="change_pending",
    )

    result = validate_workspace_placeholder(placeholder)

    assert result.ok is False
    assert "UNAPPROVED_INITIALIZATION_CHANGE" in result.errors


def test_stage00_schema_claim_attempt_is_rejected():
    placeholder = WorkspaceInitializationContextPlaceholder(
        workspace_context_id="workspace-001",
        workspace_refs=["workspace://nexus"],
        project_initialization_refs=["project://init"],
        active_wbs_ref="7.19",
        source_hash="sha256:source",
        policy_hash="sha256:policy",
        known_fields={"final_stage00_schema": "invented"},
        tbd_fields=[],
        last_human_approved_change_ref="alex-approved-change",
        placeholder_status="placeholder_validated",
    )

    result = validate_workspace_placeholder(placeholder)

    assert result.ok is False
    assert "STAGE00_SCHEMA_CLAIM_ATTEMPTED" in result.errors


def test_owner_equals_verifier_blocks_without_exception():
    result = validate_task_unit(_unit(owner="thunder", verifier="thunder"))

    assert result.ok is False
    assert "OWNER_EQUALS_VERIFIER" in result.errors


def test_no_go_drift_is_rejected():
    result = validate_task_unit(_unit(no_go_scope=[]))

    assert result.ok is False
    assert "MISSING_NO_GO_SCOPE" in result.errors


def test_task_envelope_requires_dod_and_stop_conditions():
    envelope = TaskEnvelope(
        task_id="task-001",
        envelope_version="v1",
        run_id="run-001",
        objective="Objective",
        source_refs=["wbs://7.19.2"],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
        role_target="implementer",
        required_capabilities=["code_edit"],
        dependencies=[],
        constraints=[],
        no_go_scope=["no runtime start"],
        deliverables=[],
        stop_conditions=[],
        dispatch_mode="local_only",
        idempotency_key="idem-001",
    )

    result = validate_task_envelope(envelope)

    assert result.ok is False
    assert "MISSING_DELIVERABLES" in result.errors
    assert "MISSING_STOP_CONDITIONS" in result.errors


def test_owner_handoff_packet_requires_audit_record():
    packet = OwnerHandoffPacket(
        packet_id="packet-001",
        target_owner="thunder",
        task_unit_ref="task-001",
        required_context=["context"],
        exact_input_docs=["input.md"],
        owner_local_paths=["D:/Projects/Nexus"],
        no_go_boundaries=["no runtime start"],
        expected_deliverables=["evidence"],
        validation_commands_or_evidence=["pytest"],
        due_or_timeout="manual",
        reply_format="candidate",
        stop_escalation_path="nova",
        audit_ref="",
    )

    result = validate_owner_handoff_packet(packet)

    assert result.ok is False
    assert "MISSING_AUDIT_REF" in result.errors


def test_secret_like_values_are_rejected():
    result = validate_workflow_constraints(_constraints(source_refs=["sk-" + "test-secret"]))

    assert result.ok is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)
