import json
import sys

from nexus.mq.codex_sdk_bridge_client import CodexSdkBridgeClient, CodexSdkBridgeClientConfig
from nexus.mq.codex_session_runner import CodexSessionRunRequest
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
        "required_commands": ["python -m pytest nexus/mq/tests/test_codex_sdk_bridge_client.py -q"],
        "evidence_requirements": ["sdk fake sidecar events"],
        "no_go_scope": ["no live SDK call"],
        "started_at": NOW,
    }
    data.update(overrides)
    return CodexSessionRunRequest(**data)


def test_sdk_bridge_client_maps_fake_sidecar_events_and_persists_evidence(tmp_path):
    sidecar = tmp_path / "fake_sidecar.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json, sys",
                "payload = json.loads(sys.stdin.read())",
                "print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-001'}), flush=True)",
                "print(json.dumps({'type': 'turn.completed', 'turn_id': 'turn-001'}), flush=True)",
                "print(json.dumps({'type': 'result', 'status': 'completed_execution', 'sdk_transport_status': 'completed_execution', 'inner_codex_command_runner_status': 'no_failure_observed', 'nexus_command_execution_status': 'not_classified', 'final_result_candidate_status': 'completed_execution', 'thread_id': 'thread-001', 'turn_id': 'turn-001', 'output_text': 'SDK_OK', 'evidence_refs': ['sdk://event/thread.started']}), flush=True)",
                "print('diagnostic warning', file=sys.stderr, flush=True)",
                "assert payload['run_id'] == 'run-sdk-001'",
                "assert payload['sidecar_protocol_version'] == '4.19.codex.sdk_sidecar.v1'",
                "assert payload['bounded_workdir']",
                "assert payload['evidence_root']",
                "assert payload['live_sdk_authorized'] is False",
            ]
        )
    )
    evidence_root = tmp_path / "evidence"
    client = CodexSdkBridgeClient(
        CodexSdkBridgeClientConfig(
            node_path=sys.executable,
            sidecar_path=str(sidecar),
            bounded_workdir=str(tmp_path),
            evidence_root=str(evidence_root),
            timeout_seconds=5,
        )
    )

    result = client.run(_request())

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.error_code is None
    assert result.sidecar_process_status == "exited_zero"
    assert result.sdk_transport_status == "completed_execution"
    assert result.inner_codex_command_runner_status == "no_failure_observed"
    assert result.nexus_command_execution_status == "not_classified"
    assert result.final_result_candidate_status == "completed_execution"
    assert result.thread_id == "thread-001"
    assert result.turn_id == "turn-001"
    assert [event["type"] for event in result.events] == ["thread.started", "turn.completed", "result"]
    assert result.final_result["output_text"] == "SDK_OK"
    assert "sdk-bridge://events/jsonl" in result.evidence_refs
    assert "sdk-bridge://stderr" in result.evidence_refs
    envelope = json.loads((evidence_root / "sdk_bridge_envelope.json").read_text())
    assert envelope["run_id"] == "run-sdk-001"
    assert envelope["thread_id"] == "thread-001"
    assert envelope["turn_id"] == "turn-001"
    assert envelope["exit_code"] == 0
    assert envelope["sidecar_process_status"] == "exited_zero"
    assert envelope["sdk_transport_status"] == "completed_execution"
    assert envelope["inner_codex_command_runner_status"] == "no_failure_observed"
    assert envelope["nexus_command_execution_status"] == "not_classified"
    assert envelope["final_result_candidate_status"] == "completed_execution"
    assert len([line for line in (evidence_root / "sidecar_stdout.jsonl").read_text().splitlines() if line.strip()]) == 3
    assert "diagnostic warning" in (evidence_root / "sidecar_stderr.txt").read_text()


def test_sdk_bridge_client_preserves_inner_execution_failure_status_when_process_exits_zero(tmp_path):
    sidecar = tmp_path / "blocked_sidecar.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json, sys",
                "sys.stdin.read()",
                "print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-blocked'}), flush=True)",
                "print(json.dumps({'type': 'result', 'status': 'blocked', 'error_code': 'CODEX_SDK_INNER_COMMAND_RUNNER_FAILED', 'sdk_transport_status': 'blocked', 'inner_codex_command_runner_status': 'blocked', 'nexus_command_execution_status': 'not_started', 'final_result_candidate_status': 'blocked', 'thread_id': 'thread-blocked'}), flush=True)",
            ]
        )
    )
    evidence_root = tmp_path / "blocked-evidence"
    client = CodexSdkBridgeClient(
        CodexSdkBridgeClientConfig(
            node_path=sys.executable,
            sidecar_path=str(sidecar),
            bounded_workdir=str(tmp_path),
            evidence_root=str(evidence_root),
            timeout_seconds=5,
        )
    )

    result = client.run(_request())

    assert result.exit_code == 0
    assert result.sidecar_process_status == "exited_zero"
    assert result.error_code == "CODEX_SDK_INNER_COMMAND_RUNNER_FAILED"
    assert result.sdk_transport_status == "blocked"
    assert result.inner_codex_command_runner_status == "blocked"
    assert result.nexus_command_execution_status == "not_started"
    assert result.final_result_candidate_status == "blocked"
    envelope = json.loads((evidence_root / "sdk_bridge_envelope.json").read_text())
    assert envelope["exit_code"] == 0
    assert envelope["sidecar_process_status"] == "exited_zero"
    assert envelope["sdk_transport_status"] == "blocked"
    assert envelope["inner_codex_command_runner_status"] == "blocked"
    assert envelope["nexus_command_execution_status"] == "not_started"
    assert envelope["final_result_candidate_status"] == "blocked"


def test_sdk_bridge_client_serializes_reviewed_codex_path_override_for_live_transport(tmp_path):
    sidecar = tmp_path / "capture_sidecar.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json, sys",
                "payload = json.loads(sys.stdin.read())",
                "assert payload['live_sdk_authorized'] is True",
                "assert payload['codex_path_override'] == 'C:/Users/John/AppData/Local/OpenAI/Codex/bin/codex.exe'",
                "assert payload['reviewed_codex_cli_paths'] == ['C:/Users/John/AppData/Local/OpenAI/Codex/bin/codex.exe']",
                "assert payload['reviewed_codex_cli_versions'] == ['codex-cli 0.130.0-alpha.5']",
                "assert payload['prompt_contract'] == 'minimal_non_business_probe'",
                "print(json.dumps({'type': 'result', 'status': 'blocked', 'error_code': 'CODEX_SDK_LIVE_CALL_NOT_AUTHORIZED'}), flush=True)",
            ]
        )
    )
    client = CodexSdkBridgeClient(
        CodexSdkBridgeClientConfig(
            node_path=sys.executable,
            sidecar_path=str(sidecar),
            bounded_workdir=str(tmp_path),
            timeout_seconds=5,
            live_sdk_authorized=True,
            codex_path_override="C:/Users/John/AppData/Local/OpenAI/Codex/bin/codex.exe",
            reviewed_codex_cli_versions=["codex-cli 0.130.0-alpha.5"],
            reviewed_codex_cli_paths=["C:/Users/John/AppData/Local/OpenAI/Codex/bin/codex.exe"],
            prompt_contract="minimal_non_business_probe",
        )
    )

    result = client.run(_request())

    assert result.exit_code == 0
    assert result.error_code == "CODEX_SDK_LIVE_CALL_NOT_AUTHORIZED"


def test_sdk_bridge_client_fails_closed_on_timeout_and_persists_partial_streams(tmp_path):
    sidecar = tmp_path / "slow_sidecar.py"
    sidecar.write_text(
        "\n".join(
            [
                "import json, sys, time",
                "sys.stdin.read()",
                "print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-timeout'}), flush=True)",
                "print('stderr-before-timeout', file=sys.stderr, flush=True)",
                "time.sleep(5)",
            ]
        )
    )
    evidence_root = tmp_path / "timeout-evidence"
    client = CodexSdkBridgeClient(
        CodexSdkBridgeClientConfig(
            node_path=sys.executable,
            sidecar_path=str(sidecar),
            bounded_workdir=str(tmp_path),
            evidence_root=str(evidence_root),
            timeout_seconds=1,
            post_cleanup_timeout_seconds=1,
        )
    )

    result = client.run(_request())

    assert result.timed_out is True
    assert result.exit_code is None
    assert result.error_code == "CODEX_SDK_SIDECAR_TIMEOUT"
    assert result.cleanup_command
    assert result.drain_completed is True
    assert "thread-timeout" in result.stdout_text
    assert "stderr-before-timeout" in result.stderr_text
    envelope = json.loads((evidence_root / "sdk_bridge_envelope.json").read_text())
    assert envelope["error_code"] == "CODEX_SDK_SIDECAR_TIMEOUT"
    assert envelope["timeout_seconds"] == 1
    assert envelope["cleanup"]["command"]
