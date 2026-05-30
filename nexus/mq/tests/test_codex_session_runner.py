import subprocess

from nexus.mq.codex_session_runner import (
    CliCodexSessionRunner,
    CodexCliGitStatusSnapshot,
    CodexCliPathProbeResult,
    CodexCliProcessResult,
    CodexCliRunnerConfig,
    CodexSessionRunRequest,
    DisabledCodexSessionRunner,
    filter_codex_stdout_events,
    probe_codex_cli_path,
    read_git_status_snapshot,
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
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    result = runner.run(_request())

    assert result.status == "completed_execution"
    assert result.errors == []
    assert result.started is True
    assert result.exit_code == 0
    assert result.error_code is None
    assert result.changed_file_refs == []
    assert result.disallowed_write_refs == []
    assert result.no_go_refs == []
    assert result.result_candidate_ref == "codex-result-candidate://run-codex-001/assign-codex-001/completed_execution"
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
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    result = runner.run(_request())

    assert result.status == "blocked"
    assert result.errors == ["CODEX_CLI_TIMEOUT"]
    assert result.error_code == "CODEX_CLI_TIMEOUT"
    assert result.exit_code is None
    assert result.cleanup_refs == ["codex-cli://process/cleanup-proven"]
    assert "codex-cli://process/cleanup-proven" in result.evidence_refs


def test_cli_codex_session_runner_suppresses_exact_duplicate_without_second_launch():
    calls = {"count": 0}

    def process_runner(command, *, cwd, timeout_seconds):
        calls["count"] += 1
        return CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"",
            cleanup_proven=True,
        )

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=process_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    first = runner.run(_request())
    replay = runner.run(_request())

    assert calls["count"] == 1
    assert first.status == "completed_execution"
    assert replay.status == "blocked"
    assert replay.errors == ["CODEX_DUPLICATE_SUPPRESSED"]
    assert replay.error_code == "CODEX_DUPLICATE_SUPPRESSED"
    assert replay.result_candidate_ref == first.result_candidate_ref
    assert "codex-cli://duplicate/replay-suppressed" in replay.evidence_refs


def test_cli_codex_session_runner_suppresses_changed_duplicate_without_second_launch():
    calls = {"count": 0}

    def process_runner(command, *, cwd, timeout_seconds):
        calls["count"] += 1
        return CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"",
            cleanup_proven=True,
        )

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=process_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    first = runner.run(_request())
    conflict = runner.run(_request(required_commands=["python -m pytest other.py -q"]))

    assert calls["count"] == 1
    assert first.status == "completed_execution"
    assert conflict.status == "blocked"
    assert conflict.errors == ["CODEX_DUPLICATE_SUPPRESSED"]
    assert conflict.error_code == "CODEX_DUPLICATE_SUPPRESSED"
    assert "codex-cli://duplicate/suppressed-conflict" in conflict.evidence_refs


def test_cli_codex_session_runner_dirty_worktree_guard_blocks_launch():
    calls = {"count": 0}

    def process_runner(command, *, cwd, timeout_seconds):
        calls["count"] += 1
        return CodexCliProcessResult(exit_code=0, stdout=b"", stderr=b"")

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=process_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(changed_file_refs=["nexus/mq/dirty.py"]),
    )

    result = runner.run(_request())

    assert calls["count"] == 0
    assert result.status == "blocked"
    assert result.error_code == "CODEX_DIRTY_WORKTREE"
    assert result.changed_file_refs == ["nexus/mq/dirty.py"]


def test_cli_codex_session_runner_blocks_when_pre_git_status_fails_closed():
    calls = {"count": 0}

    def process_runner(command, *, cwd, timeout_seconds):
        calls["count"] += 1
        return CodexCliProcessResult(exit_code=0, stdout=b"", stderr=b"")

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=process_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(errors=["CODEX_GIT_STATUS_TIMEOUT"]),
    )

    result = runner.run(_request())

    assert calls["count"] == 0
    assert result.status == "blocked"
    assert result.errors == ["CODEX_GIT_STATUS_TIMEOUT"]
    assert result.error_code == "CODEX_GIT_STATUS_TIMEOUT"
    assert "codex-cli://git-status/pre/unavailable" in result.evidence_refs


def test_cli_codex_session_runner_quarantines_when_post_git_status_fails_closed():
    snapshots = [
        CodexCliGitStatusSnapshot(),
        CodexCliGitStatusSnapshot(errors=["CODEX_GIT_STATUS_NONZERO_EXIT"]),
    ]

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=lambda command, *, cwd, timeout_seconds: CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"",
            cleanup_proven=True,
        ),
        git_status_reader=lambda cwd: snapshots.pop(0),
    )

    result = runner.run(_request())

    assert result.status == "quarantined"
    assert result.errors == ["CODEX_GIT_STATUS_NONZERO_EXIT"]
    assert result.error_code == "CODEX_GIT_STATUS_NONZERO_EXIT"
    assert result.drain_refs == ["codex-cli://drain/git-status-unavailable"]
    assert "codex-cli://git-status/post/unavailable" in result.evidence_refs


def test_cli_codex_session_runner_quarantines_disallowed_write_surface():
    snapshots = [
        CodexCliGitStatusSnapshot(),
        CodexCliGitStatusSnapshot(changed_file_refs=["nexus/private.txt"]),
    ]

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(cli_path="C:/Codex/bin/codex.exe", bounded_workdir="C:/bounded/workdir"),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=lambda command, *, cwd, timeout_seconds: CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"",
            cleanup_proven=True,
        ),
        git_status_reader=lambda cwd: snapshots.pop(0),
    )

    result = runner.run(_request())

    assert result.status == "quarantined"
    assert result.error_code == "CODEX_WRITE_SURFACE_VIOLATION"
    assert result.disallowed_write_refs == ["nexus/private.txt"]
    assert result.drain_refs == ["codex-cli://drain/write-surface-violation"]


def test_cli_codex_session_runner_quarantines_no_go_write_surface():
    snapshots = [
        CodexCliGitStatusSnapshot(),
        CodexCliGitStatusSnapshot(changed_file_refs=["secrets/prod.env"]),
    ]

    runner = CliCodexSessionRunner(
        config=CodexCliRunnerConfig(
            cli_path="C:/Codex/bin/codex.exe",
            bounded_workdir="C:/bounded/workdir",
            prohibited_write_surfaces=["secrets/*"],
        ),
        probe=lambda path: CodexCliPathProbeResult(path=path, version="codex-cli 0.133.0"),
        process_runner=lambda command, *, cwd, timeout_seconds: CodexCliProcessResult(
            exit_code=0,
            stdout=b'{"type":"item.completed","item":{"text":"CODEX_CLI_PROOF_OK"}}\n',
            stderr=b"",
            cleanup_proven=True,
        ),
        git_status_reader=lambda cwd: snapshots.pop(0),
    )

    result = runner.run(_request(allowed_write_surfaces=["secrets/*"]))

    assert result.status == "quarantined"
    assert result.error_code == "CODEX_NO_GO_SCOPE_VIOLATION"
    assert result.no_go_refs == ["secrets/prod.env"]
    assert result.offline_refs == ["codex-cli://offline/no-go-scope-violation"]


def test_probe_codex_cli_path_fails_closed_on_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = probe_codex_cli_path("C:/Codex/bin/codex.exe")

    assert result.errors == ["CODEX_CLI_PROBE_TIMEOUT"]


def test_probe_codex_cli_path_fails_closed_on_help_permission_error(monkeypatch):
    calls = {"count": 0}

    def fake_run(command, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return subprocess.CompletedProcess(command, 0, stdout=b"codex-cli 0.133.0", stderr=b"")
        raise PermissionError("Access is denied")

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = probe_codex_cli_path("C:/Codex/bin/codex.exe")

    assert result.errors == ["CODEX_CLI_ACCESS_DENIED"]


def test_probe_codex_cli_path_fails_closed_on_exec_help_os_error(monkeypatch):
    calls = {"count": 0}

    def fake_run(command, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return subprocess.CompletedProcess(command, 0, stdout=b"codex-cli 0.133.0", stderr=b"")
        raise OSError("missing")

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = probe_codex_cli_path("C:/Codex/bin/codex.exe")

    assert result.errors == ["CODEX_CLI_NOT_FOUND"]


def test_read_git_status_snapshot_fails_closed_on_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = read_git_status_snapshot("C:/bounded/workdir")

    assert result.changed_file_refs == []
    assert result.errors == ["CODEX_GIT_STATUS_TIMEOUT"]


def test_read_git_status_snapshot_fails_closed_on_os_error(monkeypatch):
    def fake_run(command, **kwargs):
        raise OSError("git missing")

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = read_git_status_snapshot("C:/bounded/workdir")

    assert result.changed_file_refs == []
    assert result.errors == ["CODEX_GIT_STATUS_OS_ERROR"]


def test_read_git_status_snapshot_fails_closed_on_nonzero_exit(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 128, stdout=b"", stderr=b"not a worktree")

    monkeypatch.setattr("nexus.mq.codex_session_runner.subprocess.run", fake_run)

    result = read_git_status_snapshot("C:/bounded/workdir")

    assert result.changed_file_refs == []
    assert result.errors == ["CODEX_GIT_STATUS_NONZERO_EXIT"]
