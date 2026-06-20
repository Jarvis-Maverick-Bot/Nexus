from nexus.mq.engineering_delivery_core_contracts import (
    BlockerEvidence,
    DeliveryPacket,
    EvidenceExpectation,
    Layer1TaskPublication,
    RoadmapBacklogItem,
    SourceAuthorityRef,
    TraceabilityRef,
    explain_delivery_packet_block,
    explain_publication_block,
    stable_contract_hash,
    validate_delivery_packet,
    validate_delivery_packet_supersession,
    validate_delivery_packet_transition,
    validate_publication,
    validate_publication_supersession,
    validate_publication_transition,
    validate_roadmap_backlog_item,
)


VALID_HASH = "a" * 64


def _source(**overrides):
    data = {
        "authority_id": "src-001",
        "source_type": "shared_docs",
        "source_uri": "shared-docs://edc/pr007/source",
        "source_sha256": VALID_HASH,
        "authority_actor": "nova",
    }
    data.update(overrides)
    return SourceAuthorityRef(**data)


def _expectation(**overrides):
    data = {
        "expectation_id": "evidence-001",
        "required_artifacts": ["pytest output", "source diff"],
        "validation_refs": ["python -m pytest nexus/mq/tests/test_engineering_delivery_core_contracts.py"],
        "reviewer": "nova",
    }
    data.update(overrides)
    return EvidenceExpectation(**data)


def _trace(**overrides):
    data = {
        "issue_ids": ["EDC-ISSUE-01"],
        "prd_ids": ["PRD-L1-001"],
        "spec_ids": ["SPEC-L1-001"],
        "ux_surface_ids": ["UX-L1-PUBLISH"],
        "test_case_ids": ["TC-L1-PUBLISH-001"],
        "future_evidence_ids": ["FUTURE-VERIFY-L1-PUBLISH"],
    }
    data.update(overrides)
    return TraceabilityRef(**data)


def _blocker(**overrides):
    data = {
        "reason_code": "MISSING_BOUNDARY",
        "human_readable_reason": "Scope boundary is missing.",
        "evidence_refs": ["validation://missing-boundary"],
        "recommended_action": "Add a bounded scope before review.",
    }
    data.update(overrides)
    return BlockerEvidence(**data)


def _publication(**overrides):
    data = {
        "publication_id": "pub-001",
        "title": "Publish Layer 1 task",
        "owner": "thunder",
        "source_authority": _source(),
        "issue_ids": ["EDC-ISSUE-01"],
        "evidence_expectation": _expectation(),
        "no_go_boundaries": ["no_dispatch", "no_live_start"],
        "status": "draft",
        "authority_actor": "nova",
        "authority_timestamp": "2026-06-20T00:00:00Z",
        "traceability": _trace(),
    }
    data.update(overrides)
    return Layer1TaskPublication(**data)


def _roadmap_item(**overrides):
    data = {
        "item_id": "roadmap-001",
        "source_publication_id": "pub-001",
        "title": "Create bounded DeliveryPacket intake",
        "desired_outcomes": ["one bounded packet"],
        "source_refs": ["roadmap://edc/slice001"],
        "owner": "thunder",
    }
    data.update(overrides)
    return RoadmapBacklogItem(**data)


def _packet(**overrides):
    data = {
        "packet_id": "packet-001",
        "source_publication_id": "pub-001",
        "roadmap_item_id": "roadmap-001",
        "objectives": ["one bounded packet"],
        "exclusions": ["dispatch", "evidence transport", "gate decision"],
        "evidence_expectation": _expectation(),
        "no_go_boundaries": ["no_dispatch", "no_live_start"],
        "status": "candidate",
        "traceability": _trace(
            issue_ids=["EDC-ISSUE-02"],
            prd_ids=["PRD-RB-001"],
            spec_ids=["SPEC-RB-001"],
            ux_surface_ids=["UX-RB-PACKET"],
            test_case_ids=["TC-RB-PACKET-001"],
            future_evidence_ids=["FUTURE-VERIFY-RB-PACKET"],
        ),
    }
    data.update(overrides)
    return DeliveryPacket(**data)


def test_tc_l1_publish_001_source_authority_reference_field_rejects_blank_value():
    result = validate_publication(_publication(source_authority=None))

    assert result.ok is False
    assert "MISSING_SOURCE_AUTHORITY_REF" in result.errors


def test_tc_l1_publish_002_source_authority_hash_field_rejects_malformed_value():
    result = validate_publication(_publication(source_authority=_source(source_sha256="bad-hash")))

    assert result.ok is False
    assert "INVALID_SOURCE_AUTHORITY_HASH" in result.errors


def test_tc_l1_publish_003_owner_field_rejects_empty_actor():
    result = validate_publication(_publication(owner=""))

    assert result.ok is False
    assert "MISSING_PUBLICATION_OWNER" in result.errors


def test_tc_l1_publish_004_issue_mapping_field_requires_accepted_edc_issue_id():
    result = validate_publication(_publication(issue_ids=["NOT-AN-EDC-ISSUE"]))

    assert result.ok is False
    assert "UNKNOWN_EDC_ISSUE" in result.errors


def test_tc_l1_publish_005_evidence_expectation_field_is_mandatory():
    result = validate_publication(_publication(evidence_expectation=None))

    assert result.ok is False
    assert "MISSING_EVIDENCE_EXPECTATION" in result.errors


def test_tc_l1_publish_006_no_go_boundary_reference_is_inherited_at_publication():
    publication = _publication(no_go_boundaries=["no_dispatch", "no_live_start"])

    result = validate_publication(publication)

    assert result.ok is True
    assert publication.to_dict()["no_go_boundaries"] == ["no_dispatch", "no_live_start"]


def test_tc_l1_publish_007_draft_to_published_transition_requires_layer1_authority():
    result = validate_publication_transition(
        _publication(status="draft"),
        target_status="published",
        authority_actor="nova",
        authority_timestamp="2026-06-20T00:01:00Z",
    )

    assert result.ok is True


def test_tc_l1_publish_008_draft_to_blocked_transition_records_reason_code():
    blocker = _blocker(reason_code="MISSING_SOURCE_AUTHORITY", human_readable_reason="Source authority is missing.")

    result = validate_publication_transition(
        _publication(status="draft"),
        target_status="blocked",
        authority_actor="nova",
        blocker_evidence=blocker,
    )

    assert result.ok is True
    assert result.explanations["reason_code"] == "MISSING_SOURCE_AUTHORITY"


def test_tc_l1_publish_009_published_to_withdrawn_transition_prevents_future_packet_creation():
    publication = _publication(status="withdrawn")

    result = validate_delivery_packet(_packet(), source_publication=publication, roadmap_item=_roadmap_item())

    assert result.ok is False
    assert "SOURCE_PUBLICATION_WITHDRAWN" in result.errors


def test_tc_l1_publish_010_non_authority_actor_cannot_publish_task():
    result = validate_publication_transition(
        _publication(status="draft"),
        target_status="published",
        authority_actor="agent-recommendation",
        authority_timestamp="2026-06-20T00:01:00Z",
    )

    assert result.ok is False
    assert "ACTOR_NOT_LAYER1_AUTHORITY" in result.errors


def test_tc_l1_publish_013_withdrawn_publication_cannot_reopen_as_published():
    result = validate_publication_transition(
        _publication(status="withdrawn"),
        target_status="published",
        authority_actor="nova",
        authority_timestamp="2026-06-20T00:02:00Z",
    )

    assert result.ok is False
    assert "INVALID_PUBLICATION_TRANSITION" in result.errors


def test_tc_l1_publish_014_deferred_is_not_a_layer1_publication_state():
    result = validate_publication(
        _publication(
            status="deferred",
            blocker_evidence=_blocker(revisit_condition="authority source refresh"),
        )
    )

    assert result.ok is False
    assert "INVALID_PUBLICATION_STATUS" in result.errors


def test_tc_l1_publish_011_publication_is_immutable_after_packet_binding():
    original = _publication(status="published", bound_delivery_packet_ids=["packet-001"])
    changed = _publication(title="Changed title", status="published", bound_delivery_packet_ids=["packet-001"])

    rejected = validate_publication_supersession(original, changed)
    accepted = validate_publication_supersession(
        original,
        _publication(
            publication_id="pub-002",
            supersedes_publication_id="pub-001",
            title="Changed title",
            status="published",
        ),
    )

    assert rejected.ok is False
    assert "PUBLICATION_BOUND_REQUIRES_SUPERSESSION" in rejected.errors
    assert accepted.ok is True


def test_tc_l1_publish_012_blocked_publication_explanation_is_available_through_hitl():
    publication = _publication(status="blocked", blocker_evidence=_blocker(evidence_refs=["evidence://pub/block"]))

    explanation = explain_publication_block(publication)

    assert explanation["reason_code"] == "MISSING_BOUNDARY"
    assert explanation["evidence_refs"] == ["evidence://pub/block"]


def test_tc_rb_packet_001_roadmap_item_id_is_required_for_deliverypacket_intake():
    result = validate_roadmap_backlog_item(_roadmap_item(item_id=""))

    assert result.ok is False
    assert "MISSING_ROADMAP_ITEM_ID" in result.errors


def test_tc_rb_packet_002_packet_objective_field_must_be_single_outcome():
    result = validate_delivery_packet(
        _packet(objectives=["first outcome", "second outcome"]),
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "PACKET_REQUIRES_SINGLE_OBJECTIVE" in result.errors


def test_tc_rb_packet_003_packet_exclusion_list_is_mandatory():
    result = validate_delivery_packet(
        _packet(exclusions=[]),
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "MISSING_PACKET_EXCLUSIONS" in result.errors


def test_tc_rb_packet_004_packet_evidence_expectation_carries_from_publication():
    result = validate_delivery_packet(
        _packet(evidence_expectation=_expectation(expectation_id="other-evidence")),
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "PACKET_EVIDENCE_EXPECTATION_NOT_INHERITED" in result.errors


def test_tc_rb_packet_005_candidate_to_bounded_transition_validates_scope():
    packet = _packet(status="candidate")

    result = validate_delivery_packet_transition(
        packet,
        target_status="bounded",
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is True
    assert result.explanations["scope_hash"] == stable_contract_hash(packet.scope_fields())


def test_tc_rb_packet_006_bounded_to_ready_for_roster_transition_requires_roster_precondition():
    result = validate_delivery_packet_transition(
        _packet(status="bounded"),
        target_status="ready_for_roster",
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is True
    assert "ROSTER_BASELINE_REQUIRED_BEFORE_DISPATCH" in result.warnings


def test_tc_rb_packet_013_withdrawn_packet_cannot_reopen_as_bounded():
    result = validate_delivery_packet_transition(
        _packet(status="withdrawn"),
        target_status="bounded",
        source_publication=_publication(status="published"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "INVALID_DELIVERY_PACKET_TRANSITION" in result.errors


def test_tc_rb_packet_007_unbounded_packet_transitions_to_blocked():
    packet = _packet(status="blocked", exclusions=[], blocker_evidence=_blocker(reason_code="MISSING_PACKET_EXCLUSIONS"))

    result = validate_delivery_packet(packet, source_publication=_publication(status="published"), roadmap_item=_roadmap_item())
    explanation = explain_delivery_packet_block(packet)

    assert result.ok is True
    assert explanation["reason_code"] == "MISSING_PACKET_EXCLUSIONS"


def test_tc_rb_packet_008_external_prerequisite_creates_deferred_packet_with_revisit_condition():
    packet = _packet(
        status="deferred",
        blocker_evidence=_blocker(
            reason_code="WAITING_FOR_AUTHORITY",
            human_readable_reason="Awaiting authority update.",
            revisit_condition="authority package refreshed",
        ),
    )

    result = validate_delivery_packet(packet, source_publication=_publication(status="published"), roadmap_item=_roadmap_item())

    assert result.ok is True


def test_tc_rb_packet_009_scope_widening_attempt_is_rejected():
    result = validate_delivery_packet(
        _packet(no_go_boundaries=["no_dispatch"]),
        source_publication=_publication(status="published", no_go_boundaries=["no_dispatch", "no_live_start"]),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "MISSING_INHERITED_NO_GO_BOUNDARY" in result.errors


def test_tc_rb_packet_010_withdrawn_source_publication_blocks_packet_refresh():
    result = validate_delivery_packet(
        _packet(status="candidate"),
        source_publication=_publication(status="withdrawn"),
        roadmap_item=_roadmap_item(),
    )

    assert result.ok is False
    assert "SOURCE_PUBLICATION_WITHDRAWN" in result.errors


def test_tc_rb_packet_011_packet_hash_changes_only_on_supersession():
    original = _packet(status="bounded")
    changed = _packet(objectives=["changed objective"], status="bounded")

    rejected = validate_delivery_packet_supersession(original, changed)
    accepted = validate_delivery_packet_supersession(
        original,
        _packet(packet_id="packet-002", objectives=["changed objective"], supersedes_packet_id="packet-001"),
    )

    assert rejected.ok is False
    assert "PACKET_HASH_CHANGED_WITHOUT_SUPERSESSION" in rejected.errors
    assert accepted.ok is True


def test_tc_rb_packet_012_packet_status_is_visible_in_ux_surface():
    packet = _packet(status="bounded")

    data = packet.to_dict()

    assert data["status"] == "bounded"
    assert "UX-RB-PACKET" in data["traceability"]["ux_surface_ids"]
