from nexus.mq import engineering_delivery_core_contracts as edc_contracts
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


def _roster_member(**overrides):
    data = {
        "agent_id": "agent-thunder",
        "display_name": "Thunder",
        "registration_state": "registered_active",
        "capability_tags": ["contracts", "python"],
        "authority_boundary": ["slice002", "team_roster"],
        "source_authority_ref": _source(authority_id="roster-src-001"),
        "state_reason": "Activated for bounded contract work.",
        "state_changed_by": "nova",
        "state_changed_at_utc": "2026-06-21T00:00:00Z",
    }
    data.update(overrides)
    return edc_contracts.RosterMember(**data)


def _roster_snapshot(**overrides):
    data = {
        "roster_snapshot_id": "roster-snapshot-001",
        "delivery_packet_id": "packet-001",
        "captured_at_utc": "2026-06-21T00:01:00Z",
        "source_registry_ref": _source(authority_id="registry-src-001"),
        "agent_registrations": [_roster_member()],
        "eligibility_policy_version": "SPEC-TEAM-003-v0.1",
        "snapshot_state": "captured",
    }
    data.update(overrides)
    return edc_contracts.RosterSnapshot(**data)


def _eligibility_requirement(**overrides):
    data = {
        "requirement_id": "eligibility-req-001",
        "delivery_packet_id": "packet-001",
        "required_capability_tags": ["contracts"],
        "authority_boundary": ["slice002"],
        "no_go_boundaries": ["no_dispatch_runtime"],
        "traceability": _trace(
            issue_ids=["EDC-ISSUE-03", "EDC-ISSUE-04"],
            prd_ids=["PRD-TEAM-002"],
            spec_ids=["SPEC-TEAM-003"],
            ux_surface_ids=["UX-TEAM-ROSTER"],
            test_case_ids=["TC-TEAM-ROSTER-001"],
            future_evidence_ids=["FUTURE-VERIFY-TEAM-ELIGIBILITY"],
        ),
    }
    data.update(overrides)
    return edc_contracts.RosterEligibilityRequirement(**data)


def _roster_transition(**overrides):
    data = {
        "agent_id": "agent-thunder",
        "from_state": "registered_passive",
        "to_state": "registered_active",
        "authority_actor": "nova",
        "authority_timestamp": "2026-06-21T00:02:00Z",
        "evidence_refs": ["registry://agent-thunder/activation"],
        "reason": "Authorized activation.",
    }
    data.update(overrides)
    return edc_contracts.RosterStateTransition(**data)


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


def test_tc_l1_publish_015_blocked_publication_cannot_transition_to_published():
    result = validate_publication_transition(
        _publication(status="blocked", blocker_evidence=_blocker()),
        target_status="published",
        authority_actor="nova",
        authority_timestamp="2026-06-21T00:01:00Z",
    )

    assert result.ok is False
    assert "INVALID_PUBLICATION_TRANSITION" in result.errors


def test_tc_l1_publish_016_blocked_publication_can_return_to_draft():
    result = validate_publication_transition(
        _publication(status="blocked", blocker_evidence=_blocker()),
        target_status="draft",
        authority_actor="nova",
    )

    assert result.ok is True


def test_tc_l1_publish_017_draft_publication_cannot_transition_to_withdrawn():
    result = validate_publication_transition(
        _publication(status="draft"),
        target_status="withdrawn",
        authority_actor="nova",
        authority_timestamp="2026-06-21T00:02:00Z",
    )

    assert result.ok is False
    assert "INVALID_PUBLICATION_TRANSITION" in result.errors


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


def test_tc_team_roster_001_roster_snapshot_is_required_before_eligibility_evaluation():
    result = edc_contracts.evaluate_roster_eligibility(None, _eligibility_requirement())

    assert result.ok is False
    assert "MISSING_ROSTER_SNAPSHOT" in result.errors
    assert result.explanations["eligible_agent_ids"] == []


def test_tc_team_roster_002_registered_active_state_can_enter_eligibility_pool():
    result = edc_contracts.evaluate_roster_eligibility(_roster_snapshot(), _eligibility_requirement())

    assert result.ok is True
    assert result.explanations["eligible_agent_ids"] == ["agent-thunder"]
    assert result.explanations["decisions"][0]["eligible"] is True


def test_tc_team_roster_003_registered_passive_state_is_planning_visible_only():
    snapshot = _roster_snapshot(agent_registrations=[_roster_member(registration_state="registered_passive")])

    result = edc_contracts.evaluate_roster_eligibility(snapshot, _eligibility_requirement())

    assert result.ok is False
    assert result.explanations["decisions"][0]["agent_id"] == "agent-thunder"
    assert "AGENT_PLANNING_VISIBLE_ONLY" in result.explanations["decisions"][0]["exclusion_reasons"]


def test_tc_team_roster_004_unavailable_state_excludes_otherwise_matching_member():
    snapshot = _roster_snapshot(agent_registrations=[_roster_member(registration_state="unavailable")])

    result = edc_contracts.evaluate_roster_eligibility(snapshot, _eligibility_requirement())

    assert result.ok is False
    assert "AGENT_UNAVAILABLE" in result.explanations["decisions"][0]["exclusion_reasons"]


def test_tc_team_roster_005_suspended_state_excludes_member_from_all_dispatch_eligibility():
    snapshot = _roster_snapshot(agent_registrations=[_roster_member(registration_state="suspended")])

    result = edc_contracts.evaluate_roster_eligibility(snapshot, _eligibility_requirement())

    assert result.ok is False
    assert "AGENT_SUSPENDED" in result.explanations["decisions"][0]["exclusion_reasons"]


def test_tc_team_roster_006_unregistered_identity_cannot_be_selected():
    snapshot = _roster_snapshot(
        agent_registrations=[_roster_member(registration_state="unregistered", capability_tags=[], authority_boundary=[])]
    )

    result = edc_contracts.evaluate_roster_eligibility(snapshot, _eligibility_requirement())

    assert result.ok is False
    reasons = result.explanations["decisions"][0]["exclusion_reasons"]
    assert "AGENT_UNREGISTERED" in reasons
    assert "MISSING_REQUIRED_CAPABILITY" not in reasons


def test_tc_team_roster_007_capability_match_is_required_for_active_member():
    result = edc_contracts.evaluate_roster_eligibility(
        _roster_snapshot(),
        _eligibility_requirement(required_capability_tags=["contracts", "python"]),
    )

    assert result.ok is True
    assert result.explanations["decisions"][0]["matched_capabilities"] == ["contracts", "python"]


def test_tc_team_roster_008_capability_mismatch_blocks_active_member():
    result = edc_contracts.evaluate_roster_eligibility(
        _roster_snapshot(),
        _eligibility_requirement(required_capability_tags=["contracts", "rust"]),
    )

    assert result.ok is False
    assert "MISSING_REQUIRED_CAPABILITY" in result.explanations["decisions"][0]["exclusion_reasons"]
    assert result.explanations["eligible_agent_ids"] == []


def test_tc_team_roster_009_authority_band_match_is_required():
    result = edc_contracts.evaluate_roster_eligibility(
        _roster_snapshot(),
        _eligibility_requirement(authority_boundary=["slice002", "team_roster"]),
    )

    assert result.ok is True
    assert result.explanations["decisions"][0]["matched_authority_boundary"] == ["slice002", "team_roster"]


def test_tc_team_roster_010_authority_mismatch_prevents_dispatch_even_with_capability_match():
    result = edc_contracts.evaluate_roster_eligibility(
        _roster_snapshot(),
        _eligibility_requirement(authority_boundary=["slice003"]),
    )

    assert result.ok is False
    assert "AUTHORITY_BOUNDARY_MISMATCH" in result.explanations["decisions"][0]["exclusion_reasons"]


def test_tc_team_roster_011_roster_snapshot_hash_binds_eligibility_decision():
    snapshot = _roster_snapshot()

    result = edc_contracts.evaluate_roster_eligibility(snapshot, _eligibility_requirement())
    decision = edc_contracts.RosterEligibilityDecision(**result.explanations["decisions"][0])

    assert decision.roster_snapshot_hash == snapshot.snapshot_hash()
    assert edc_contracts.validate_roster_eligibility_decision(decision, snapshot).ok is True


def test_tc_team_roster_012_roster_state_transition_requires_evidence_pointer():
    missing_evidence = edc_contracts.validate_roster_state_transition(_roster_transition(evidence_refs=[]))
    allowed_transition = edc_contracts.validate_roster_state_transition(_roster_transition())
    direct_activation = edc_contracts.validate_roster_state_transition(
        _roster_transition(
            from_state="unregistered",
            to_state="registered_active",
            evidence_refs=["registry://agent-thunder/registration-and-activation"],
        )
    )

    assert missing_evidence.ok is False
    assert "MISSING_ROSTER_TRANSITION_EVIDENCE" in missing_evidence.errors
    assert allowed_transition.ok is True
    assert direct_activation.ok is False
    assert "INVALID_ROSTER_STATE_TRANSITION" in direct_activation.errors


def test_tc_team_roster_013_stale_roster_snapshot_is_rejected():
    result = edc_contracts.evaluate_roster_eligibility(
        _roster_snapshot(snapshot_state="stale"),
        _eligibility_requirement(),
    )

    assert result.ok is False
    assert "ROSTER_SNAPSHOT_NOT_CURRENT" in result.errors


def test_tc_team_roster_014_human_can_ask_why_no_agent_is_eligible():
    snapshot = _roster_snapshot(
        agent_registrations=[
            _roster_member(agent_id="agent-passive", registration_state="registered_passive"),
            _roster_member(agent_id="agent-active", capability_tags=["docs"], authority_boundary=["slice002"]),
        ]
    )

    explanation = edc_contracts.explain_no_eligible_agent(snapshot, _eligibility_requirement(required_capability_tags=["python"]))

    assert explanation["reason_code"] == "NO_ELIGIBLE_AGENT"
    assert "AGENT_PLANNING_VISIBLE_ONLY" in explanation["roster_state_gaps"]
    assert "MISSING_REQUIRED_CAPABILITY" in explanation["capability_gaps"]
    assert explanation["advisory_only"] is True


def _l2_trace(**overrides):
    data = {
        "issue_ids": ["EDC-ISSUE-04"],
        "prd_ids": ["PRD-L2-001", "PRD-L2-002", "PRD-L2-003", "PRD-L2-004"],
        "spec_ids": ["SPEC-L2-001", "SPEC-L2-002", "SPEC-L2-003", "SPEC-L2-004"],
        "ux_surface_ids": ["UX-L2-DISPATCH", "UX-TEAM-ROSTER", "UX-HITL-DIALOGUE"],
        "test_case_ids": ["TC-L2-DISPATCH-001"],
        "future_evidence_ids": ["FUTURE-VERIFY-L2-DISPATCH"],
    }
    data.update(overrides)
    return TraceabilityRef(**data)


def _ready_l2_packet(**overrides):
    data = {
        "status": "ready_for_roster",
        "objectives": ["plan one bounded Layer 2 WorkItem"],
        "exclusions": ["live dispatch assignment", "evidence transport", "gate decision"],
        "no_go_boundaries": ["no_dispatch_runtime", "no_gate_decision"],
        "traceability": _l2_trace(test_case_ids=["TC-L2-DISPATCH-001"]),
    }
    data.update(overrides)
    return _packet(**data)


def _work_item(**overrides):
    data = {
        "work_item_id": "packet-001/work-001",
        "delivery_packet_id": "packet-001",
        "source_publication_id": "pub-001",
        "work_title": "Plan bounded WorkItem recommendation",
        "work_scope": "contract-only Layer 2 planning record",
        "required_capabilities": ["contracts"],
        "authority_boundary": ["slice003"],
        "inherited_no_go_control_ids": ["no_dispatch_runtime", "no_gate_decision"],
        "output_contract": ["WorkItem contract record", "DispatchRecommendation contract record"],
        "evidence_contract": ["focused pytest output", "source diff", "traceability artifact"],
        "evidence_expectation_id": "evidence-001",
        "state": "proposed",
        "correlation_root_id": "packet-001",
        "traceability": _l2_trace(),
        "source_issue_ids": ["EDC-ISSUE-04"],
        "decomposition_reason": "Split the DeliveryPacket into one bounded Layer 2 planning responsibility.",
        "requirement_ids": ["PRD-L2-001", "SPEC-L2-001"],
    }
    data.update(overrides)
    return edc_contracts.WorkItem(**data)


def _decomposition_plan(*work_items, **overrides):
    data = {
        "decomposition_plan_id": "decomp-001",
        "delivery_packet_id": "packet-001",
        "work_items": list(work_items) or [_work_item()],
        "decomposed_by": "layer2-planner",
        "decomposed_at_utc": "2026-06-21T01:00:00Z",
        "decomposition_order": [
            "packet_validation",
            "work_item_boundary_validation",
            "roster_evaluation",
            "advisory_recommendation",
        ],
    }
    data.update(overrides)
    return edc_contracts.WorkItemDecompositionPlan(**data)


def _l2_roster_snapshot(**overrides):
    data = {
        "delivery_packet_id": "packet-001",
        "agent_registrations": [
            _roster_member(capability_tags=["contracts", "python"], authority_boundary=["slice003", "team_roster"])
        ],
    }
    data.update(overrides)
    return _roster_snapshot(**data)


def _l2_eligibility_requirement(**overrides):
    data = {
        "required_capability_tags": ["contracts"],
        "authority_boundary": ["slice003"],
        "no_go_boundaries": ["no_dispatch_runtime"],
        "traceability": _l2_trace(
            prd_ids=["PRD-TEAM-001", "PRD-TEAM-004", "PRD-L2-002"],
            spec_ids=["SPEC-TEAM-001", "SPEC-TEAM-004", "SPEC-L2-003"],
            ux_surface_ids=["UX-L2-DISPATCH", "UX-TEAM-ROSTER"],
            test_case_ids=["TC-L2-DISPATCH-006"],
        ),
    }
    data.update(overrides)
    return _eligibility_requirement(**data)


def _eligible_result(snapshot=None):
    return edc_contracts.evaluate_roster_eligibility(snapshot or _l2_roster_snapshot(), _l2_eligibility_requirement())


def _dispatch_recommendation(**overrides):
    work_item = overrides.pop("work_item", _work_item())
    snapshot = overrides.pop("roster_snapshot", _l2_roster_snapshot())
    eligibility_result = overrides.pop("eligibility_result", _eligible_result(snapshot))
    data = {
        "work_item": work_item,
        "roster_snapshot": snapshot,
        "eligibility_result": eligibility_result,
        "selected_agent_id": "agent-thunder",
        "selected_agent_reason": "agent-thunder is the only eligible registered_active member for the WorkItem.",
        "decided_by": "layer2-planner",
        "decided_at_utc": "2026-06-21T01:01:00Z",
    }
    data.update(overrides)
    return edc_contracts.create_dispatch_recommendation(**data)


def test_tc_l2_dispatch_001_workitem_parent_packet_id_is_mandatory():
    result = edc_contracts.validate_work_item(_work_item(delivery_packet_id=""), parent_packet=_ready_l2_packet())

    assert result.ok is False
    assert "MISSING_WORK_ITEM_PARENT_PACKET_ID" in result.errors


def test_tc_l2_dispatch_002_workitem_carries_inherited_issue_mapping():
    packet = _ready_l2_packet()
    work_item = _work_item(source_issue_ids=["EDC-ISSUE-04"], traceability=_l2_trace(issue_ids=["EDC-ISSUE-04"]))

    result = edc_contracts.validate_work_item(work_item, parent_packet=packet)

    assert result.ok is True
    assert work_item.source_issue_ids == ["EDC-ISSUE-04"]


def test_tc_l2_dispatch_003_workitem_carries_inherited_evidence_expectation():
    packet = _ready_l2_packet()
    work_item = _work_item(evidence_expectation_id=packet.evidence_expectation.expectation_id)

    result = edc_contracts.validate_work_item(work_item, parent_packet=packet)

    assert result.ok is True
    assert work_item.evidence_contract == ["focused pytest output", "source diff", "traceability artifact"]


def test_tc_l2_dispatch_004_decomposition_cannot_widen_packet_boundary():
    packet = _ready_l2_packet()
    widened = _work_item(
        inherited_no_go_control_ids=["no_dispatch_runtime"],
        source_issue_ids=["EDC-ISSUE-04", "EDC-ISSUE-05"],
    )

    result = edc_contracts.validate_work_item_decomposition(_decomposition_plan(widened), parent_packet=packet)

    assert result.ok is False
    assert "WORK_ITEM_NO_GO_BOUNDARY_NOT_INHERITED" in result.errors
    assert "WORK_ITEM_SOURCE_ISSUE_NOT_INHERITED" in result.errors


def test_tc_l2_dispatch_005_packet_validation_precedes_roster_evaluation():
    not_ready_packet = _ready_l2_packet(status="bounded")

    blocked = edc_contracts.validate_work_item_decomposition(_decomposition_plan(), parent_packet=not_ready_packet)
    ready = edc_contracts.validate_work_item_decomposition(_decomposition_plan(), parent_packet=_ready_l2_packet())

    assert blocked.ok is False
    assert "PACKET_NOT_READY_FOR_ROSTER" in blocked.errors
    assert ready.ok is True
    assert ready.explanations["ordering"][0] == "packet_validation"


def test_tc_l2_dispatch_006_roster_eligibility_precedes_selected_agent():
    snapshot = _l2_roster_snapshot(agent_registrations=[_roster_member(registration_state="registered_passive")])
    eligibility_result = edc_contracts.evaluate_roster_eligibility(snapshot, _l2_eligibility_requirement())

    recommendation = _dispatch_recommendation(roster_snapshot=snapshot, eligibility_result=eligibility_result)
    result = edc_contracts.validate_dispatch_recommendation(
        recommendation,
        work_item=_work_item(),
        roster_snapshot=snapshot,
        eligibility_result=eligibility_result,
    )

    assert result.ok is False
    assert "SELECTED_AGENT_REQUIRES_ELIGIBILITY_PROOF" in result.errors


def test_tc_l2_dispatch_007_selected_agent_records_snapshot_and_reason():
    snapshot = _l2_roster_snapshot()
    recommendation = _dispatch_recommendation(roster_snapshot=snapshot)

    result = edc_contracts.validate_dispatch_recommendation(
        recommendation,
        work_item=_work_item(),
        roster_snapshot=snapshot,
        eligibility_result=_eligible_result(snapshot),
    )

    assert result.ok is True
    assert recommendation.roster_snapshot_id == snapshot.roster_snapshot_id
    assert recommendation.selected_agent_reason


def test_tc_l2_dispatch_008_no_eligible_agent_creates_blocked_dispatch():
    snapshot = _l2_roster_snapshot(agent_registrations=[_roster_member(registration_state="registered_passive")])
    eligibility_result = edc_contracts.evaluate_roster_eligibility(snapshot, _l2_eligibility_requirement())

    recommendation = edc_contracts.create_dispatch_recommendation(
        work_item=_work_item(),
        roster_snapshot=snapshot,
        eligibility_result=eligibility_result,
        decided_by="layer2-planner",
        decided_at_utc="2026-06-21T01:02:00Z",
    )
    explanation = edc_contracts.explain_dispatch_recommendation(recommendation)

    assert recommendation.decision_state == "blocked"
    assert recommendation.selected_agent_id is None
    assert "NO_ELIGIBLE_AGENT" in recommendation.blocked_reason
    assert explanation["reason_code"] == "NO_ELIGIBLE_AGENT"


def test_tc_l2_dispatch_009_temporary_external_constraint_creates_deferred_dispatch():
    recommendation = edc_contracts.create_dispatch_recommendation(
        work_item=_work_item(),
        roster_snapshot=_l2_roster_snapshot(),
        eligibility_result=_eligible_result(),
        decided_by="layer2-planner",
        decided_at_utc="2026-06-21T01:03:00Z",
        external_constraint_reason="TEMPORARY_EXTERNAL_CONSTRAINT",
        external_revisit_condition="operator clears the dependency",
    )

    assert recommendation.decision_state == "deferred"
    assert recommendation.deferred_reason == "TEMPORARY_EXTERNAL_CONSTRAINT"
    assert recommendation.external_revisit_condition == "operator clears the dependency"


def test_tc_l2_dispatch_010_agent_recommendation_does_not_become_dispatch_authority():
    recommendation = _dispatch_recommendation(advisory_only=False)

    result = edc_contracts.validate_dispatch_recommendation(
        recommendation,
        work_item=_work_item(),
        roster_snapshot=_l2_roster_snapshot(),
        eligibility_result=_eligible_result(),
    )

    assert result.ok is False
    assert "DISPATCH_RECOMMENDATION_MUST_REMAIN_ADVISORY" in result.errors


def test_tc_l2_dispatch_011_dispatch_evidence_links_to_workitem_hash():
    work_item = _work_item()
    recommendation = _dispatch_recommendation(work_item=work_item)

    result = edc_contracts.validate_dispatch_recommendation(
        recommendation,
        work_item=work_item,
        roster_snapshot=_l2_roster_snapshot(),
        eligibility_result=_eligible_result(),
    )

    assert result.ok is True
    assert recommendation.work_item_hash == work_item.work_item_hash()


def test_tc_l2_dispatch_012_dispatch_cannot_start_from_packetless_request():
    result = edc_contracts.validate_work_item(_work_item(), parent_packet=None)

    assert result.ok is False
    assert "MISSING_PARENT_DELIVERY_PACKET" in result.errors


def _l3_trace(**overrides):
    data = {
        "issue_ids": ["EDC-ISSUE-05"],
        "prd_ids": ["PRD-L3-001", "PRD-L3-002", "PRD-L3-003", "PRD-GATE-001"],
        "spec_ids": ["SPEC-L3-001", "SPEC-L3-002", "SPEC-L3-003", "SPEC-GATE-001"],
        "ux_surface_ids": ["UX-L3-EVIDENCE", "UX-GATE-RECEIPT", "UX-HITL-DIALOGUE", "UX-TRACEABILITY"],
        "test_case_ids": ["TC-L3-EVIDENCE-001"],
        "future_evidence_ids": ["FUTURE-VERIFY-L3-EVIDENCE"],
    }
    data.update(overrides)
    return TraceabilityRef(**data)


def _evidence_ref(**overrides):
    data = {
        "evidence_ref_id": "evidence-ref-001",
        "artifact_uri": "evidence://packet-001/work-001/pytest-output",
        "content_sha256": VALID_HASH,
        "producer": "agent-thunder",
        "produced_at_utc": "2026-06-21T02:00:00Z",
        "source_work_item_id": "packet-001/work-001",
    }
    data.update(overrides)
    return edc_contracts.EvidenceReference(**data)


def _evidence_envelope(**overrides):
    data = {
        "envelope_id": "envelope-001",
        "correlation_root_id": "packet-001",
        "delivery_packet_id": "packet-001",
        "work_item_id": "packet-001/work-001",
        "dispatch_decision_id": "dispatch-rec::packet-001/work-001::roster-snapshot-001",
        "agent_id": "agent-thunder",
        "event_type": "evidence_available",
        "sequence_number": 1,
        "idempotency_key": "idem-packet-001-work-001-seq-1",
        "evidence_refs": [_evidence_ref()],
        "transport_status": "created",
        "business_status": "in_progress",
        "created_at_utc": "2026-06-21T02:01:00Z",
        "traceability": _l3_trace(),
    }
    data.update(overrides)
    return edc_contracts.EvidenceEnvelope(**data)


def _transport_state(**overrides):
    data = {
        "transport_state_id": "transport-state-001",
        "envelope_id": "envelope-001",
        "work_item_id": "packet-001/work-001",
        "dispatch_decision_id": "dispatch-rec::packet-001/work-001::roster-snapshot-001",
        "correlation_root_id": "packet-001",
        "idempotency_key": "idem-packet-001-work-001-seq-1",
        "sequence_number": 1,
        "status": "created",
        "event_type": "evidence_available",
        "attempt_number": 1,
        "observed_at_utc": "2026-06-21T02:02:00Z",
    }
    data.update(overrides)
    return edc_contracts.EvidenceTransportState(**data)


def test_tc_l3_evidence_001_evidence_envelope_requires_envelope_id():
    result = edc_contracts.validate_evidence_envelope(
        _evidence_envelope(envelope_id=""),
        work_item=_work_item(),
        dispatch_recommendation=_dispatch_recommendation(),
        parent_packet=_ready_l2_packet(),
    )

    assert result.ok is False
    assert "MISSING_EVIDENCE_ENVELOPE_ID" in result.errors


def test_tc_l3_evidence_002_evidence_envelope_requires_parent_workitem_id():
    result = edc_contracts.validate_evidence_envelope(
        _evidence_envelope(work_item_id=""),
        work_item=_work_item(),
        dispatch_recommendation=_dispatch_recommendation(),
        parent_packet=_ready_l2_packet(),
    )

    assert result.ok is False
    assert "MISSING_EVIDENCE_PARENT_WORK_ITEM_ID" in result.errors


def test_tc_l3_evidence_003_correlation_id_binds_transport_state_to_workitem():
    work_item = _work_item()
    envelope = _evidence_envelope(correlation_root_id=work_item.correlation_root_id)
    state = _transport_state(correlation_root_id=envelope.correlation_root_id)

    result = edc_contracts.validate_evidence_transport_state(
        state,
        envelope=envelope,
        work_item=work_item,
        dispatch_recommendation=_dispatch_recommendation(work_item=work_item),
    )

    assert result.ok is True
    assert result.explanations["correlation_root_id"] == work_item.correlation_root_id
    assert result.explanations["work_item_id"] == work_item.work_item_id


def test_tc_l3_evidence_004_idempotency_key_suppresses_duplicate_envelope():
    original = _evidence_envelope(envelope_id="envelope-original")
    duplicate = _evidence_envelope(envelope_id="envelope-duplicate")

    result = edc_contracts.evaluate_evidence_idempotency(duplicate, [original])

    assert result.ok is True
    assert result.explanations["action"] == "duplicate_ignored"
    assert result.explanations["original_envelope_id"] == "envelope-original"
    assert "DUPLICATE_EVIDENCE_ENVELOPE_IGNORED" in result.warnings


def test_tc_l3_evidence_005_ack_state_is_not_delivery_truth():
    result = edc_contracts.validate_ack_not_delivery_truth(
        _transport_state(status="acknowledged", event_type="dispatch_received")
    )

    assert result.ok is True
    assert result.explanations["not_delivery_truth"] is True
    assert result.explanations["receipt_available"] is False


def test_tc_l3_evidence_006_timeout_schedules_retry_without_package_completion():
    envelope = _evidence_envelope(event_type="transport_timeout", transport_status="timed_out")
    timed_out = _transport_state(
        status="timed_out",
        event_type="transport_timeout",
        timeout_class="soft_timeout",
        evidence_package_complete=False,
    )
    retrying = _transport_state(
        transport_state_id="transport-state-retry",
        status="retrying",
        event_type="retry_scheduled",
        attempt_number=2,
        prior_state="timed_out",
        prior_envelope_id="envelope-001",
        retry_after_utc="2026-06-21T02:05:00Z",
        evidence_package_complete=False,
    )

    result = edc_contracts.validate_evidence_transport_transition(timed_out, retrying, envelope=envelope)

    assert result.ok is True
    assert result.explanations["retry_scheduled"] is True
    assert result.explanations["evidence_package_complete"] is False


def test_tc_l3_evidence_007_transport_failure_is_distinct_from_gate_blocker():
    result = edc_contracts.validate_transport_non_authority(
        _transport_state(status="failed", event_type="transport_failed", failure_reason="TRANSPORT_UNAVAILABLE")
    )

    assert result.ok is True
    assert result.explanations["transport_failure_is_gate_blocker"] is False
    assert result.explanations["gate_outcome_created"] is False


def test_tc_l3_evidence_008_replay_keeps_prior_evidence_lineage():
    prior = _evidence_envelope(envelope_id="envelope-prior")
    replay = _evidence_envelope(
        envelope_id="envelope-replay",
        replay_of_envelope_id="envelope-prior",
        attempt_number=2,
    )

    result = edc_contracts.validate_evidence_replay_lineage(replay, prior_envelope=prior)

    assert result.ok is True
    assert result.explanations["replay_of_envelope_id"] == "envelope-prior"


def test_tc_l3_evidence_009_supersession_marks_current_evidence_without_deleting_prior():
    superseded = _evidence_envelope(
        envelope_id="envelope-old",
        transport_status="superseded",
        superseded_by_envelope_id="envelope-current",
    )
    current = _evidence_envelope(envelope_id="envelope-current", supersedes_envelope_id="envelope-old")

    result = edc_contracts.validate_evidence_supersession(superseded, current)

    assert result.ok is True
    assert result.explanations["visible_envelope_ids"] == ["envelope-old", "envelope-current"]


def test_tc_l3_evidence_010_evidence_available_updates_package_only():
    result = edc_contracts.validate_transport_non_authority(
        _transport_state(
            status="evidence_available",
            event_type="evidence_available",
            evidence_package_complete=True,
            gate_state="pending",
            receipt_state="pending_gate",
        )
    )

    assert result.ok is True
    assert result.explanations["evidence_package_complete"] is True
    assert result.explanations["gate_state"] == "pending"
    assert result.explanations["receipt_available"] is False


def test_tc_l3_evidence_010_transport_state_cannot_imply_gate_or_receipt_authority():
    receipt_issuable = edc_contracts.validate_transport_non_authority(_transport_state(receipt_state="issuable"))
    gate_approved = edc_contracts.validate_transport_non_authority(_transport_state(gate_state="approved"))

    assert receipt_issuable.ok is False
    assert "TRANSPORT_STATUS_CANNOT_IMPLY_DELIVERY_RECEIPT_AUTHORITY" in receipt_issuable.errors
    assert gate_approved.ok is False
    assert "TRANSPORT_STATUS_CANNOT_IMPLY_GATE_DECISION_AUTHORITY" in gate_approved.errors


def test_tc_l3_evidence_005_ack_state_with_issuable_receipt_fails_closed():
    result = edc_contracts.validate_ack_not_delivery_truth(
        _transport_state(status="acknowledged", event_type="dispatch_received", receipt_state="issuable")
    )

    assert result.ok is False
    assert "TRANSPORT_STATUS_CANNOT_IMPLY_DELIVERY_RECEIPT_AUTHORITY" in result.errors
    assert result.explanations["not_delivery_truth"] is True


def test_tc_l3_evidence_011_missing_content_hash_blocks_evidence_package_inclusion():
    result = edc_contracts.validate_evidence_reference(_evidence_ref(content_sha256=""))

    assert result.ok is False
    assert "MISSING_EVIDENCE_CONTENT_HASH" in result.errors
    assert result.explanations["inclusion_state"] == "excluded"
    assert result.explanations["exclusion_reason"] == "missing_content_hash"


def test_tc_l3_evidence_012_content_hash_mismatch_blocks_evidence_package_inclusion():
    result = edc_contracts.validate_evidence_reference(
        _evidence_ref(content_sha256="a" * 64, actual_content_sha256="b" * 64)
    )

    assert result.ok is False
    assert "EVIDENCE_CONTENT_HASH_MISMATCH" in result.errors
    assert result.explanations["inclusion_state"] == "excluded"
    assert result.explanations["evidence_package_complete"] is False
