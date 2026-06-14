from __future__ import annotations

from dataclasses import replace
from typing import Any

from nexus.governance.app_contract import (
    NotesEvidenceFrameViewModel,
    WorkspacePickerOverlayViewModel,
    build_read_only_desktop_shell,
    validate_local_desktop_shell,
    validate_notes_evidence_frame,
    validate_workspace_picker_overlay,
)
from nexus.governance.delivery_feedback import (
    validate_completion_continuity_packet,
    validate_delivery_record,
    validate_feedback_metric_extraction,
    validate_feedback_metric_trend,
    validate_feedback_record,
    validate_feedback_triage_decision,
    validate_feedback_triage_decision_request,
    validate_next_cycle_proposal,
)
from nexus.governance.dispatch_contract import (
    validate_dispatch_decision,
    validate_dispatch_readiness_inputs,
    validate_dispatch_readiness_review,
    validate_handoff_candidate,
    validate_returned_blocked_reason,
    validate_returned_result_candidate,
)
from nexus.governance.execution import (
    validate_approved_plan_ref,
    validate_layer1_workpacket,
    validate_packet_dependency_graph,
    validate_packet_map,
    validate_packet_readiness_decision,
)
from nexus.governance.impact_control import (
    validate_impact_assessment,
    validate_impact_control_request,
    validate_impact_review_task_request,
    validate_layer_impact_detected,
    validate_lower_layer_request_candidate,
    validate_lower_layer_request_outcome,
)
from nexus.governance.kernel import GovernanceKernel
from nexus.governance.monitor_hitl import (
    validate_component_return_action,
    validate_deliverable_evaluation_result,
    validate_escalation_progress_gate,
    validate_human_decision,
    validate_human_review_task,
    validate_review_disposition,
)
from nexus.governance.no_go import NoGoBoundaryPolicy
from nexus.governance.service_facade import CommandDraft, GovernanceServiceFacade
from nexus.governance.source_authority import verify_source_authority
from nexus.governance.standardization import validate_standardization_bundle
from nexus.governance.workspace_init import validate_workspace_manifest

from ..test_source_authority import valid_manifest as valid_source_manifest
from . import delivery_feedback as delivery
from . import dispatch_contract as dispatch
from . import execution
from . import impact_control as impact
from . import monitor_hitl as monitor
from . import service_facade as service_fx
from . import standardization
from . import workspace_init


POSITIVE_COMPONENTS: tuple[str, ...] = (
    "source_authority",
    "workspace_init",
    "standardization",
    "project_execution",
    "dispatch_contract",
    "monitor_hitl",
    "impact_control",
    "delivery_feedback",
    "governance_service",
    "local_app_contract",
)

REQUIRED_NEGATIVE_FAMILIES: tuple[str, ...] = (
    "stale_wbs_source_authority",
    "workspace_final_status",
    "missing_evaluation_profile",
    "workpacket_submitted_state",
    "handoff_controller_execution",
    "monitor_workpacket_execution",
    "lower_layer_submission",
    "raw_feedback_mutation",
    "projection_as_authority",
    "local_app_view_model_authority",
)


def build_positive_dry_run_trace() -> dict[str, Any]:
    steps = (
        _step(
            "source_authority",
            ("SourceAuthorityManifest",),
            ("WBS V0.6", "parent Solution Design V0.8.5"),
            (verify_source_authority(valid_source_manifest()),),
        ),
        _step(
            "workspace_init",
            ("WorkspaceManifest", "GovernanceSurfaceIndex"),
            workspace_init.SOURCE_REFS,
            (validate_workspace_manifest(workspace_init.valid_manifest()),),
        ),
        _step(
            "standardization",
            ("ExecutionPlanCandidate", "DeliverableEvaluationProfile", "FeedbackMetricPolicy"),
            standardization.SOURCE_REFS,
            (
                validate_standardization_bundle(
                    plan=standardization.valid_execution_plan(),
                    profiles=(standardization.valid_profile(),),
                    feedback_policy=standardization.valid_feedback_policy(),
                    feedback_driven_change=True,
                ),
            ),
        ),
        _step(
            "project_execution",
            ("ApprovedExecutionPlanCandidateRef", "PacketMap", "Layer1WorkPacket", "PacketReadinessDecision"),
            execution.SOURCE_REFS,
            (
                validate_approved_plan_ref(execution.valid_approved_plan_ref()),
                validate_packet_map(execution.valid_packet_map()),
                validate_packet_dependency_graph(execution.valid_dependency_graph()),
                validate_layer1_workpacket(execution.valid_workpacket()),
                validate_packet_readiness_decision(execution.valid_readiness_decision()),
            ),
        ),
        _step(
            "dispatch_contract",
            ("DispatchReadinessReview", "DispatchDecision", "DispatchControllerHandoffCandidate"),
            dispatch.DISPATCH_SOURCE_REFS,
            (
                validate_dispatch_readiness_inputs(
                    packet=dispatch.kernel_ready_workpacket(),
                    capability=dispatch.valid_capability_profile(),
                    transport_constraints=(dispatch.valid_transport_constraint(),),
                    context=dispatch.valid_dispatch_context(),
                    kernel_packet_record_ref=dispatch.KERNEL_PACKET_RECORD_REF,
                ),
                validate_dispatch_readiness_review(dispatch.valid_readiness_review()),
                validate_dispatch_decision(dispatch.valid_dispatch_decision()),
                validate_handoff_candidate(dispatch.valid_handoff_candidate()),
                validate_returned_result_candidate(dispatch.valid_result_candidate()),
                validate_returned_blocked_reason(dispatch.valid_blocked_reason()),
            ),
        ),
        _step(
            "monitor_hitl",
            ("HumanReviewTask", "HumanDecision", "DeliverableEvaluationResult", "ReviewDisposition"),
            monitor.MONITOR_SOURCE_REFS,
            (
                validate_human_review_task(monitor.valid_review_task()),
                validate_human_decision(monitor.valid_human_decision()),
                validate_deliverable_evaluation_result(monitor.valid_evaluation_result()),
                validate_escalation_progress_gate(()),
                validate_review_disposition(monitor.valid_review_disposition()),
                validate_component_return_action(monitor.valid_return_action()),
            ),
        ),
        _step(
            "impact_control",
            ("ImpactControlRequest", "ImpactAssessment", "LowerLayerRequestCandidate"),
            impact.IMPACT_SOURCE_REFS,
            (
                validate_impact_control_request(impact.valid_impact_request()),
                validate_impact_assessment(impact.valid_assessment()),
                validate_layer_impact_detected(impact.valid_layer_impact()),
                validate_impact_review_task_request(impact.valid_review_task_request()),
                validate_lower_layer_request_candidate(impact.valid_lower_layer_candidate()),
                validate_lower_layer_request_outcome(impact.valid_lower_layer_outcome()),
            ),
        ),
        _step(
            "delivery_feedback",
            ("DeliveryRecord", "FeedbackMetricExtraction", "FeedbackTriageDecision", "CompletionContinuityPacket"),
            delivery.DELIVERY_SOURCE_REFS,
            (
                validate_delivery_record(delivery.valid_delivery_record(), delivery.valid_accepted_increment()),
                validate_feedback_record(delivery.valid_feedback_record()),
                validate_feedback_metric_extraction(delivery.valid_extraction(), delivery.valid_policy()),
                validate_feedback_metric_trend(delivery.valid_trend(), delivery.valid_policy()),
                validate_feedback_triage_decision_request(delivery.valid_triage_request()),
                validate_feedback_triage_decision(delivery.valid_triage_decision()),
                validate_completion_continuity_packet(delivery.valid_completion_packet()),
                validate_next_cycle_proposal(delivery.valid_next_cycle_proposal()),
            ),
        ),
        _service_step(),
        _local_app_step(),
    )
    return {
        "accepted": all(step["accepted"] for step in steps),
        "canonical_authority": "GovernanceKernel",
        "live_execution_invoked": False,
        "service_boundary": "GovernanceService",
        "steps": steps,
        "terminal_state": "dry_run_evidence_ready",
    }


def build_negative_fixture_results() -> tuple[dict[str, Any], ...]:
    return (
        _negative(
            "stale_wbs_source_authority",
            "source_authority",
            verify_source_authority(valid_source_manifest(wbs_version="V0.4")),
        ),
        _negative(
            "workspace_final_status",
            "workspace_init",
            validate_workspace_manifest(workspace_init.valid_manifest(status="final_pass")),
        ),
        _negative(
            "missing_evaluation_profile",
            "standardization",
            validate_standardization_bundle(
                plan=standardization.valid_execution_plan(),
                profiles=(),
                feedback_policy=standardization.valid_feedback_policy(),
            ),
        ),
        _negative(
            "workpacket_submitted_state",
            "project_execution",
            validate_layer1_workpacket(execution.valid_workpacket(status="submitted")),
        ),
        _negative(
            "handoff_controller_execution",
            "dispatch_contract",
            validate_handoff_candidate(dispatch.valid_handoff_candidate(expected_outputs=("controller execution",))),
        ),
        _negative(
            "monitor_workpacket_execution",
            "monitor_hitl",
            validate_human_review_task(monitor.valid_review_task(recommended_next_action="please execute workpacket now")),
        ),
        _negative(
            "lower_layer_submission",
            "impact_control",
            validate_impact_control_request(impact.valid_impact_request(proposed_action="send lower layer request")),
        ),
        _negative(
            "raw_feedback_mutation",
            "delivery_feedback",
            validate_feedback_record(delivery.valid_feedback_record(raw_summary="please mutate backlog now")),
        ),
        _negative(
            "projection_as_authority",
            "governance_service",
            _service().handle(
                service_fx.service_command(
                    payload={
                        "authorization_source": "projection:mission_control",
                        "authority_source": "projection",
                    }
                )
            ),
        ),
        _negative(
            "local_app_view_model_authority",
            "local_app_contract",
            validate_local_desktop_shell(
                replace(
                    build_read_only_desktop_shell(
                        workspace_id="ws-421",
                        workspace_display_name="Layer 1 Governance",
                        kernel_source_ref="kernel:39001610",
                    ),
                    canonical_authority=True,
                )
            ),
        ),
    )


def _service_step() -> dict[str, Any]:
    draft = CommandDraft(
        draft_id="dry-run-draft-011",
        command_type="SubmitCommandDraft",
        target_ref="layer1-governance",
        payload={"requested_action": "prepare_fixture_review_packet"},
        read_only_blocked=False,
        source_refs=service_fx.SERVICE_SOURCE_REFS,
        draft_status="draft",
        created_by="agent:thunder",
    )
    response = _service().handle(service_fx.service_command(payload={"command_draft": draft.__dict__}))
    return _step(
        "governance_service",
        ("CommandDraft", "CommandEnvelope", "ServiceCommandOutcome"),
        service_fx.SERVICE_SOURCE_REFS,
        (response,),
    )


def _local_app_step() -> dict[str, Any]:
    shell = build_read_only_desktop_shell(
        workspace_id="ws-421",
        workspace_display_name="Layer 1 Governance",
        kernel_source_ref="kernel:39001610",
    )
    overlay = WorkspacePickerOverlayViewModel(
        overlay_id="workspace-picker-011",
        trigger="header_workspace_dropdown",
        mode="temporary_overlay",
        open_mode="read_only_preview",
        show_archived_parked=False,
        current_workspace_ref="Workspace:ws-421",
        recent_workspace_refs=("Workspace:ws-421",),
        active_workspace_refs=("Workspace:ws-421",),
        archived_or_parked_workspace_refs=(),
        freshness_by_workspace={"Workspace:ws-421": "current"},
        actions=("open_read_only", "cancel"),
        creates_authority=False,
        persistent_left_rail=False,
    )
    notes = NotesEvidenceFrameViewModel(
        frame_id="notes-evidence-011",
        source_docs_read=("UX V0.2-CS requirements", "Slice 010 package"),
        prototype_refs=("ux-v0.2-cs-client",),
        figma_refs=("figma:review-direction-only",),
        ux_only_status="evidence_only",
        governance_boundaries=("not authority", "not app screen", "no canonical mutation"),
        open_questions=(),
        is_app_screen=False,
        creates_authority=False,
    )
    return _step(
        "local_app_contract",
        ("LocalDesktopShellViewModel", "WorkspacePickerOverlayViewModel", "NotesEvidenceFrameViewModel"),
        ("WBS V0.6", "L1GOV-SLICE-010", "PR18:39001610"),
        (
            validate_local_desktop_shell(shell),
            validate_workspace_picker_overlay(overlay),
            validate_notes_evidence_frame(notes),
        ),
    )


def _service() -> GovernanceServiceFacade:
    return GovernanceServiceFacade(
        source_manifest=valid_source_manifest(),
        no_go_policy=NoGoBoundaryPolicy.default(),
        kernel=GovernanceKernel(),
    )


def _step(
    component: str,
    contract_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    results: tuple[Any, ...],
) -> dict[str, Any]:
    accepted = all(_is_accepted(result) for result in results)
    error_codes = tuple(code for code in (_error_code(result) for result in results) if code)
    return {
        "accepted": accepted,
        "component": component,
        "contract_refs": list(contract_refs),
        "error_code": None if accepted else (error_codes[0] if error_codes else "ERR_INVALID_TRANSITION"),
        "evidence_id": f"l1gov-slice-011/{component}.json",
        "mode": "deterministic_fixture",
        "records_appended": 0,
        "source_refs": list(source_refs),
    }


def _negative(family: str, blocked_by: str, result: Any) -> dict[str, Any]:
    return {
        "accepted": _is_accepted(result),
        "blocked_by": blocked_by,
        "error_code": _error_code(result) or "ERR_INVALID_TRANSITION",
        "family": family,
        "live_execution_invoked": False,
        "records_appended": 0,
    }


def _is_accepted(result: Any) -> bool:
    if hasattr(result, "accepted"):
        return bool(result.accepted)
    if hasattr(result, "status"):
        return str(result.status) == "accepted"
    return False


def _error_code(result: Any) -> str | None:
    code = getattr(result, "error_code", None)
    if code is None:
        return None
    return getattr(code, "value", str(code))
