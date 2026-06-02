from nexus.mq.codex_sdk_bridge_client import CodexSdkBridgeResult
from nexus.mq.codex_sdk_runner import CodexSdkRunnerConfig, SdkCodexSessionRunner
from nexus.mq.codex_session_runner import CodexCliGitStatusSnapshot, CodexSessionRunRequest
from nexus.mq.tests.test_codex_runtime_adapter import NOW


def _request(**overrides):
    data = {
        "run_id": "run-sdk-001",
        "assignment_id": "assign-sdk-001",
        "task_id": "task-sdk-001",
        "runtime_instance_id": "codex-sdk-runtime-001",
        "workspace_ref": "workspace://nexus",
        "repo_ref": "repo://nexus",
        "allowed_write_surfaces": ["nexus/mq/codex_*.py"],
        "allowed_tools": ["git", "pytest"],
        "required_commands": ["python -m pytest nexus/mq/tests/test_codex_sdk_runner.py -q"],
        "evidence_requirements": ["sdk fake runner"],
        "no_go_scope": ["no live SDK call"],
        "started_at": NOW,
    }
    data.update(overrides)
    return CodexSessionRunRequest(**data)


def test_sdk_runner_maps_fake_bridge_success_without_claiming_business_completion():
    calls = {"count": 0}

    def bridge_runner(request):
        calls["count"] += 1
        return CodexSdkBridgeResult(
            exit_code=0,
            events=[{"type": "thread.started", "thread_id": "thread-001"}],
            final_result={
                "status": "completed_execution",
                "thread_id": "thread-001",
                "turn_id": "turn-001",
                "evidence_refs": ["sdk-bridge://events/jsonl"],
            },
            evidence_refs=["sdk-bridge://events/jsonl", "sdk-bridge://result"],
            thread_id="thread-001",
            turn_id="turn-001",
        )

    runner = SdkCodexSessionRunner(
        config=CodexSdkRunnerConfig(bounded_workdir="C:/bounded/workdir"),
        bridge_runner=bridge_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    result = runner.run(_request())

    assert calls["count"] == 1
    assert result.status == "completed_execution"
    assert result.errors == []
    assert result.started is True
    assert result.live_execution_started is False
    assert result.not_business_completion is True
    assert result.result_candidate_ref == "codex-result-candidate://run-sdk-001/assign-sdk-001/completed_execution"
    assert "sdk-bridge://events/jsonl" in result.evidence_refs


def test_sdk_runner_suppresses_exact_duplicate_without_second_sidecar_call():
    calls = {"count": 0}

    def bridge_runner(request):
        calls["count"] += 1
        return CodexSdkBridgeResult(
            exit_code=0,
            final_result={"status": "completed_execution"},
            evidence_refs=["sdk-bridge://result"],
        )

    runner = SdkCodexSessionRunner(
        config=CodexSdkRunnerConfig(bounded_workdir="C:/bounded/workdir"),
        bridge_runner=bridge_runner,
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    first = runner.run(_request())
    replay = runner.run(_request())

    assert first.status == "completed_execution"
    assert calls["count"] == 1
    assert replay.status == "blocked"
    assert replay.error_code == "CODEX_DUPLICATE_SUPPRESSED"
    assert replay.started is False


def test_sdk_runner_fails_closed_on_timeout_from_sidecar():
    runner = SdkCodexSessionRunner(
        config=CodexSdkRunnerConfig(bounded_workdir="C:/bounded/workdir"),
        bridge_runner=lambda request: CodexSdkBridgeResult(
            exit_code=None,
            timed_out=True,
            error_code="CODEX_SDK_SIDECAR_TIMEOUT",
            evidence_refs=["sdk-bridge://timeout/envelope"],
        ),
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    result = runner.run(_request())

    assert result.status == "blocked"
    assert result.error_code == "CODEX_SDK_SIDECAR_TIMEOUT"
    assert result.errors == ["CODEX_SDK_SIDECAR_TIMEOUT"]
    assert "sdk-bridge://timeout/envelope" in result.evidence_refs


def test_sdk_runner_propagates_inner_sdk_command_runner_failure():
    runner = SdkCodexSessionRunner(
        config=CodexSdkRunnerConfig(bounded_workdir="C:/bounded/workdir"),
        bridge_runner=lambda request: CodexSdkBridgeResult(
            exit_code=0,
            sidecar_process_status="exited_zero",
            sdk_transport_status="blocked",
            inner_codex_command_runner_status="blocked",
            nexus_command_execution_status="not_started",
            final_result_candidate_status="blocked",
            final_result={
                "status": "blocked",
                "error_code": "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED",
                "sdk_transport_status": "blocked",
                "inner_codex_command_runner_status": "blocked",
                "nexus_command_execution_status": "not_started",
                "final_result_candidate_status": "blocked",
            },
            evidence_refs=["sdk-bridge://result", "sdk-bridge://events/jsonl"],
        ),
        git_status_reader=lambda cwd: CodexCliGitStatusSnapshot(),
    )

    result = runner.run(_request())

    assert result.status == "blocked"
    assert result.exit_code == 0
    assert result.error_code == "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED"
    assert result.errors == ["CODEX_SDK_INNER_COMMAND_RUNNER_FAILED"]
    assert result.sidecar_process_status == "exited_zero"
    assert result.sdk_transport_status == "blocked"
    assert result.inner_codex_command_runner_status == "blocked"
    assert result.nexus_command_execution_status == "not_started"
    assert result.final_result_candidate_status == "blocked"
    assert result.result_candidate_ref == "codex-result-candidate://run-sdk-001/assign-sdk-001/blocked"


def test_sdk_runner_quarantines_disallowed_writes_after_sidecar_result():
    calls = {"count": 0}

    def git_status_reader(cwd):
        calls["count"] += 1
        if calls["count"] == 1:
            return CodexCliGitStatusSnapshot()
        return CodexCliGitStatusSnapshot(changed_file_refs=["outside/nope.txt", "nexus/mq/codex_sdk_runner.py"])

    runner = SdkCodexSessionRunner(
        config=CodexSdkRunnerConfig(bounded_workdir="C:/bounded/workdir"),
        bridge_runner=lambda request: CodexSdkBridgeResult(
            exit_code=0,
            final_result={"status": "completed_execution"},
            evidence_refs=["sdk-bridge://result"],
        ),
        git_status_reader=git_status_reader,
    )

    result = runner.run(_request())

    assert result.status == "quarantined"
    assert result.error_code == "CODEX_WRITE_SURFACE_VIOLATION"
    assert result.disallowed_write_refs == ["outside/nope.txt"]
