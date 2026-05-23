from nexus.mq.structured_task_llm_advisory import (
    build_llm_advisory_context,
    validate_llm_advisory_output,
)
from nexus.mq.agent_registry_events import secret_material_errors


def test_llm_receives_only_bounded_source_context():
    context = build_llm_advisory_context(
        source_refs=["wbs://7.19.1"],
        deterministic_fields={"objective": "Implement controller", "secret": "drop-me"},
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
    )

    assert context.source_refs == ["wbs://7.19.1"]
    assert context.eligible_candidate_ids == ["thunder"]
    assert "secret" not in context.deterministic_fields


def test_llm_context_removes_top_level_secret_marker_keys():
    context = build_llm_advisory_context(
        source_refs=["wbs://7.19.1"],
        deterministic_fields={"objective": "Implement controller", "api_key": "opaque-ref"},
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
    )

    assert context.deterministic_fields == {"objective": "Implement controller"}
    assert secret_material_errors(context.deterministic_fields, path="deterministic_fields") == []


def test_llm_context_removes_nested_secret_marker_keys():
    context = build_llm_advisory_context(
        source_refs=["wbs://7.19.1"],
        deterministic_fields={
            "objective": "Implement controller",
            "nested": {"token": "opaque-ref", "route": "thunder"},
        },
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
    )

    assert context.deterministic_fields == {
        "objective": "Implement controller",
        "nested": {"route": "thunder"},
    }
    assert secret_material_errors(context.deterministic_fields, path="deterministic_fields") == []


def test_llm_context_removes_secret_like_values():
    context = build_llm_advisory_context(
        source_refs=["wbs://7.19.1"],
        deterministic_fields={
            "objective": "Implement controller",
            "source_hint": "sk-" + "reviewer-owned-secret",
        },
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
    )

    assert context.deterministic_fields == {"objective": "Implement controller"}
    assert secret_material_errors(context.deterministic_fields, path="deterministic_fields") == []


def test_llm_owner_not_eligible_rejected():
    result = validate_llm_advisory_output(
        output={"suggested_owner_id": "jarvis", "summary": "Route to jarvis"},
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
        telemetry_ref="telemetry://call-001",
    )

    assert result.ok is False
    assert "LLM_OWNER_NOT_ELIGIBLE" in result.errors


def test_scope_expansion_rejected():
    result = validate_llm_advisory_output(
        output={"suggested_owner_id": "thunder", "added_scope": ["deploy"]},
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no deploy"],
        telemetry_ref="telemetry://call-001",
    )

    assert result.ok is False
    assert "LLM_SCOPE_EXPANSION_REJECTED" in result.errors


def test_missing_wrapper_telemetry_is_evidence_gap_not_zero_usage():
    result = validate_llm_advisory_output(
        output={"suggested_owner_id": "thunder", "summary": "ok"},
        eligible_candidate_ids=["thunder"],
        no_go_scope=["no runtime start"],
        telemetry_ref="",
    )

    assert result.ok is False
    assert "MISSING_MODEL_CALL_TELEMETRY" in result.errors
