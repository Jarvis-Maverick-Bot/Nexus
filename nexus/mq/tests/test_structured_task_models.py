from nexus.mq.structured_task_models import (
    OwnerHandoffPacket,
    TaskEnvelope,
    TaskUnit,
    WorkflowConstraintSet,
)


def test_wbs7192_required_object_fields_round_trip():
    constraints = WorkflowConstraintSet(
        constraint_id="constraint-001",
        source_refs=["wbs://7.19.1"],
        wbs_refs=["7.19.7"],
        gate_state="open",
        dependency_state="satisfied",
        dod=["focused tests"],
        no_go_scope=["no runtime start"],
        evidence_requirements=["test logs"],
        review_authority_refs=["nova-review"],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
    )

    data = constraints.to_dict()

    assert data["constraint_id"] == "constraint-001"
    assert data["not_business_completion"] is True


def test_task_unit_requires_control_fields_shape():
    unit = TaskUnit(
        task_id="task-001",
        parent_id=None,
        title="Implement deterministic validation",
        objective="Validate source authority",
        source_refs=["wbs://7.19.2"],
        source_hash="sha256:source",
        owner="thunder",
        verifier="nova",
        dependencies=[],
        priority="normal",
        status="draft",
        dod=["validation fails closed"],
        no_go_scope=["no LLM authority"],
        allowed_tools=["pytest"],
        allowed_write_surfaces=["nexus/mq/structured_task_*.py"],
        evidence_requirements=["focused test log"],
        stop_conditions=["source conflict"],
        escalation_conditions=["ambiguous owner"],
    )

    assert unit.owner != unit.verifier
    assert unit.not_business_completion is True
    assert "no LLM authority" in unit.no_go_scope


def test_owner_handoff_packet_is_candidate_not_acceptance():
    packet = OwnerHandoffPacket(
        packet_id="packet-001",
        target_owner="thunder",
        task_unit_ref="task-001",
        required_context=["source refs"],
        exact_input_docs=["solution-design.md"],
        owner_local_paths=["D:/Projects/Nexus"],
        no_go_boundaries=["no live dispatch"],
        expected_deliverables=["implementation evidence"],
        validation_commands_or_evidence=["python -m pytest"],
        due_or_timeout="manual-review",
        reply_format="result candidate",
        stop_escalation_path="nova-review",
        audit_ref="audit-001",
    )

    assert packet.not_business_completion is True
    assert packet.audit_ref == "audit-001"


def test_task_envelope_preserves_source_and_policy_hashes():
    envelope = TaskEnvelope(
        task_id="task-001",
        envelope_version="v1",
        run_id="run-001",
        objective="Build handoff controller",
        source_refs=["wbs://7.19.1"],
        source_hash="sha256:source",
        policy_hash="sha256:policy",
        role_target="implementer",
        required_capabilities=["code_edit"],
        dependencies=[],
        constraints=["no runtime start"],
        no_go_scope=["no business execution"],
        deliverables=["source implementation evidence"],
        stop_conditions=["missing authority"],
        dispatch_mode="local_only",
        idempotency_key="idem-001",
    )

    assert envelope.source_hash == "sha256:source"
    assert envelope.policy_hash == "sha256:policy"
    assert envelope.not_business_completion is True
