from nexus.mq.codex_session_runner import (
    CodexSessionRunRequest,
    DisabledCodexSessionRunner,
    validate_codex_session_run_request,
)
from nexus.mq.tests.test_codex_runtime_adapter import NOW


def _request(**overrides):
    data = {
        "run_id": "run-codex-001",
        "assignment_id": "assign-codex-001",
        "task_id": "task-codex-001",
        "runtime_instance_id": "codex-runtime-001",
        "workspace_ref": "workspace://nexus",
        "repo_ref": "repo://nexus",
        "allowed_write_surfaces": ["nexus/mq/codex_*.py"],
        "allowed_tools": ["git", "pytest"],
        "required_commands": ["python -m pytest nexus/mq/tests/test_codex_session_runner.py -q"],
        "evidence_requirements": ["focused tests"],
        "no_go_scope": ["no live worker start"],
        "started_at": NOW,
    }
    data.update(overrides)
    return CodexSessionRunRequest(**data)


def test_codex_session_run_request_validates_bounded_non_business_context():
    result = validate_codex_session_run_request(_request())

    assert result.valid is True
    assert result.errors == []


def test_codex_session_run_request_rejects_secret_like_command_and_missing_write_surface():
    result = validate_codex_session_run_request(
        _request(required_commands=["echo token=" + "abc123"], allowed_write_surfaces=[])
    )

    assert result.valid is False
    assert "MISSING_CODEX_SESSION_RUN_FIELD: allowed_write_surfaces" in result.errors
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)


def test_disabled_codex_session_runner_never_starts_live_codex():
    result = DisabledCodexSessionRunner().run(_request())

    assert result.status == "blocked"
    assert result.errors == ["CODEX_SESSION_RUNNER_DISABLED"]
    assert result.live_execution_started is False
    assert result.not_business_completion is True
