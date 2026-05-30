from nexus.mq.codex_session_runner import (
    CliCodexSessionRunner,
    CodexCliPathProbeResult,
    CodexCliProcessResult,
    CodexCliRunnerConfig,
    CodexSessionRunRequest,
    DisabledCodexSessionRunner,
    filter_codex_stdout_events,
    select_codex_cli_path,
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


def test_select_codex_cli_path_prefers_configured_path_when_contract_passes():
    def probe(path):
        return CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0")

    result = select_codex_cli_path(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe"),
        discovered_candidates=["C:/Other/codex.exe"],
        probe=probe,
    )

    assert result.selected_path == "C:/Codex/bin/codex.exe"
    assert result.selected_version == "codex-cli 0.133.0"
    assert result.errors == []


def test_select_codex_cli_path_discovers_newest_passing_appdata_candidate():
    def probe(path):
        if path.endswith("old/codex.exe"):
            return CodexCliPathProbeResult(path=path, version="codex-cli 0.130.0-alpha.5")
        return CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0")

    result = select_codex_cli_path(
        config=CodexCliRunnerConfig(),
        discovered_candidates=[
            "C:/Users/John/AppData/Local/OpenAI/Codex/bin/old/codex.exe",
            "C:/Users/John/AppData/Local/OpenAI/Codex/bin/new/codex.exe",
        ],
        probe=probe,
    )

    assert result.selected_path == "C:/Users/John/AppData/Local/OpenAI/Codex/bin/new/codex.exe"
    assert result.selected_version == "codex-cli 0.133.0"
    assert result.errors == []


def test_select_codex_cli_path_fails_closed_on_windowsapps_access_denied():
    result = select_codex_cli_path(
        config=CodexCliRunnerConfig(),
        discovered_candidates=["C:/Program Files/WindowsApps/OpenAI.Codex/app/resources/codex.exe"],
        probe=lambda path: CodexCliPathProbeResult(path=path, errors=["CODEX_CLI_ACCESS_DENIED"]),
    )

    assert result.selected_path is None
    assert result.errors == ["CODEX_CLI_ACCESS_DENIED"]


def test_select_codex_cli_path_fails_closed_on_ambiguous_appdata_candidates():
    result = select_codex_cli_path(
        config=CodexCliRunnerConfig(),
        discovered_candidates=["C:/Codex/bin/a/codex.exe", "C:/Codex/bin/b/codex.exe"],
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
    )

    assert result.selected_path is None
    assert result.errors == ["CODEX_CLI_AMBIGUOUS_CANDIDATES"]


def test_filter_codex_stdout_events_tolerates_bom_and_separates_taskkill_chatter():
    stdout = (
        b"\xef\xbb\xbf{\"type\":\"thread.started\"}\r\n"
        b"{\"type\":\"item.completed\",\"item\":{\"text\":\"CODEX_CLI_PROOF_OK\"}}\r\n"
        b"SUCCESS: The process with PID 1 has been terminated.\r\n"
    )

    filtered = filter_codex_stdout_events(stdout)

    assert [event["type"] for event in filtered.events] == ["thread.started", "item.completed"]
    assert filtered.non_json_stdout == ["SUCCESS: The process with PID 1 has been terminated."]
    assert filtered.errors == []


def test_cli_codex_session_runner_maps_successful_process_to_result_candidate_evidence():
    def probe(path):
        return CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0")

    def process_runner(command, *, cwd, timeout_seconds):
        assert command[:5] == ["C:/Codex/bin/codex.exe", "--sandbox", "read-only", "--ask-for-approval", "never"]
        assert cwd == "C:/bounded/workdir"
        assert timeout_seconds == 30
        return CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"warning only",
            cleanup_proven=True,
        )

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(
            cli_path="C:/Codex/bin/codex.exe",
            bounded_workdir="C:/bounded/workdir",
            timeout_seconds=30,
        ),
        probe=probe,
        process_runner=process_runner,
    )

    result = runner.run(_request())

    assert result.status == "completed_execution"
    assert result.errors == []
    assert result.live_execution_started is False
    assert result.not_business_completion is True
    assert "codex-cli://C:/Codex/bin/codex.exe@codex-cli 0.133.0" in result.evidence_refs
    assert "codex-cli://stdout/events/1" in result.evidence_refs


def test_cli_codex_session_runner_reports_timeout_and_cleanup_without_pass_claim():
    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=lambda command, *, cwd, timeout_seconds: CodexCliProcessResult(
            exit_code=None,
            stdout=b"",
            stderr=b"timeout",
            timed_out=True,
            cleanup_proven=True,
        ),
    )

    result = runner.run(_request())

    assert result.status == "blocked"
    assert result.errors == ["CODEX_CLI_TIMEOUT"]
    assert "codex-cli://process/cleanup-proven" in result.evidence_refs
