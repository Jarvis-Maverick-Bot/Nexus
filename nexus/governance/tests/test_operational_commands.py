from __future__ import annotations

from nexus.governance.operational_commands import (
    validate_agent_runtime_command_projection,
    validate_agent_definition_record,
    validate_operational_command_draft,
    validate_runtime_instance_record,
    validate_runtime_provider_profile,
    validate_run_session_record,
)
from nexus.governance.tests.fixtures.operational_commands import (
    agent_definition,
    command_draft,
    dispatch_candidate,
    handoff_preview,
    run_session,
    runtime_instance,
    runtime_provider,
)


def test_valid_command_draft_projection_keeps_agent_runtime_and_session_separate() -> None:
    result = validate_agent_runtime_command_projection(
        agents=(agent_definition(),),
        runtime_providers=(runtime_provider(),),
        runtime_instances=(runtime_instance(),),
        run_sessions=(run_session(),),
        command_drafts=(command_draft(),),
        dispatch_candidates=(dispatch_candidate(),),
        handoff_previews=(handoff_preview(),),
    )

    assert result.accepted is True
    assert result.blocked_reasons == ()


def test_agent_runtime_session_identity_confusion_is_rejected() -> None:
    confused_session = run_session(run_session_id="agent.codex.execution")

    result = validate_agent_runtime_command_projection(
        agents=(agent_definition(),),
        runtime_providers=(runtime_provider(),),
        runtime_instances=(runtime_instance(),),
        run_sessions=(confused_session,),
        command_drafts=(command_draft(),),
        dispatch_candidates=(dispatch_candidate(),),
        handoff_previews=(handoff_preview(),),
    )

    assert result.accepted is False
    assert "run_session_id must not equal agent_id" in result.blocked_reasons


def test_command_draft_rejects_live_dispatch_and_runtime_claims() -> None:
    draft = command_draft(
        command_type="dispatch_live",
        live_dispatch_claimed=True,
        runtime_startup_claimed=True,
        blocked_authorities=("runtime_startup",),
    )

    result = validate_operational_command_draft(draft)

    assert result.accepted is False
    assert "unsupported command_type: dispatch_live" in result.blocked_reasons
    assert "command draft cannot claim live dispatch" in result.blocked_reasons
    assert "command draft cannot claim runtime startup" in result.blocked_reasons
    assert "blocked_authorities must include live_dispatch" in result.blocked_reasons


def test_command_draft_requires_handoff_writeback_and_evidence_fields() -> None:
    draft = command_draft(
        handoff_preview_ref="",
        write_back_location="",
        evidence_requirements=(),
        required_approvals=(),
    )

    result = validate_operational_command_draft(draft)

    assert result.accepted is False
    assert set(result.missing_fields) >= {
        "required_approvals",
        "evidence_requirements",
        "handoff_preview_ref",
        "write_back_location",
    }


def test_command_draft_rejects_internal_github_pr_id_confusion() -> None:
    result = validate_operational_command_draft(
        command_draft(work_item_id="36", github_pr_number=36)
    )

    assert result.accepted is False
    assert "work_item_id must use EDC-PR-###" in result.blocked_reasons
    assert "work_item_id must not equal GitHub PR number" in result.blocked_reasons


def test_runtime_provider_blocks_openclaw_as_executable_reference() -> None:
    provider = runtime_provider(provider_id="runtime-provider.openclaw.live", provider_family="openclaw", executable=True)

    result = validate_runtime_provider_profile(provider)

    assert result.accepted is False
    assert "OpenClaw provider is reference-only in EDC-PR-011" in result.blocked_reasons


def test_runtime_instance_rejects_authorized_startup_dependency_broker_and_dispatch() -> None:
    instance = runtime_instance(
        startup_allowed=True,
        dependency_install_allowed=True,
        broker_mutation_allowed=True,
        live_dispatch_allowed=True,
    )

    result = validate_runtime_instance_record(instance, provider=runtime_provider())

    assert result.accepted is False
    assert "runtime startup must remain blocked" in result.blocked_reasons
    assert "dependency install must remain blocked" in result.blocked_reasons
    assert "broker/NATS mutation must remain blocked" in result.blocked_reasons
    assert "live dispatch must remain blocked" in result.blocked_reasons


def test_individual_records_validate_when_complete() -> None:
    assert validate_agent_definition_record(agent_definition()).accepted is True
    assert validate_runtime_provider_profile(runtime_provider()).accepted is True
    assert validate_runtime_instance_record(runtime_instance(), provider=runtime_provider()).accepted is True
    assert validate_run_session_record(run_session()).accepted is True

def test_valid_edc_pr_011_command_draft_keeps_github_pr_unset_before_mapping_sync() -> None:
    draft = command_draft()

    result = validate_operational_command_draft(draft)

    assert result.accepted is True
    assert draft.work_item_id == "EDC-PR-011"
    assert draft.github_pr_number is None


def test_projection_rejects_command_draft_run_session_and_handoff_work_item_mismatch() -> None:
    result = validate_agent_runtime_command_projection(
        agents=(agent_definition(),),
        runtime_providers=(runtime_provider(),),
        runtime_instances=(runtime_instance(),),
        run_sessions=(run_session(work_item_id="EDC-PR-010"),),
        command_drafts=(command_draft(),),
        dispatch_candidates=(dispatch_candidate(),),
        handoff_previews=(handoff_preview(work_item_id="EDC-PR-010"),),
    )

    assert result.accepted is False
    assert "command draft work_item_id must match referenced run session" in result.blocked_reasons
    assert "command draft work_item_id must match referenced handoff preview" in result.blocked_reasons


def test_projection_rejects_dispatch_candidate_reference_mismatches() -> None:
    result = validate_agent_runtime_command_projection(
        agents=(agent_definition(),),
        runtime_providers=(runtime_provider(),),
        runtime_instances=(runtime_instance(),),
        run_sessions=(run_session(),),
        command_drafts=(command_draft(),),
        dispatch_candidates=(
            dispatch_candidate(
                work_item_id="EDC-PR-010",
                agent_id="agent.missing",
                runtime_instance_id="runtime.missing",
            ),
        ),
        handoff_previews=(handoff_preview(),),
    )

    assert result.accepted is False
    assert "dispatch candidate work_item_id must match command draft work item" in result.blocked_reasons
    assert "dispatch candidate agent_id must reference an agent definition" in result.blocked_reasons
    assert "dispatch candidate runtime_instance_id must reference a runtime instance" in result.blocked_reasons
