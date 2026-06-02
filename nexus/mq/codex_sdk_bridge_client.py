"""Bounded Codex SDK sidecar client for WBS 7.19.13.

The Python side remains the policy and evidence authority. This client only
launches a local sidecar process, exchanges a JSON request, and captures the
sidecar's JSONL event stream for the SDK runner.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from nexus.mq.codex_session_runner import (
    CodexSessionRunRequest,
    _kill_process_tree_result,
    _process_tree_snapshot,
    _redact_command,
    _redact_text,
    _stream_excerpt,
    _timeout_stderr,
    _timeout_stdout,
    _write_text,
)


@dataclass
class CodexSdkBridgeClientConfig:
    node_path: str
    sidecar_path: str
    bounded_workdir: str
    timeout_seconds: int = 120
    post_cleanup_timeout_seconds: int = 5
    evidence_root: Optional[str] = None
    stream_excerpt_bytes: int = 65536
    sidecar_protocol_version: str = "4.19.codex.sdk_sidecar.v1"
    live_sdk_authorized: bool = False
    codex_path_override: Optional[str] = None
    reviewed_codex_cli_versions: list[str] = field(default_factory=list)
    reviewed_codex_cli_paths: list[str] = field(default_factory=list)
    prompt_contract: Optional[str] = None


@dataclass
class CodexSdkBridgeResult:
    exit_code: Optional[int]
    events: list[dict[str, Any]] = field(default_factory=list)
    final_result: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    error_code: Optional[str] = None
    timed_out: bool = False
    pid: Optional[int] = None
    command: list[str] = field(default_factory=list)
    started_at: Optional[str] = None
    timeout_at: Optional[str] = None
    cleanup_started_at: Optional[str] = None
    cleanup_ended_at: Optional[str] = None
    ended_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    timeout_seconds: Optional[int] = None
    post_cleanup_timeout_seconds: Optional[int] = None
    cleanup_proven: bool = False
    cleanup_command: list[str] = field(default_factory=list)
    cleanup_exit_code: Optional[int] = None
    cleanup_stdout: bytes = b""
    cleanup_stderr: bytes = b""
    process_tree_before_cleanup: Optional[str] = None
    process_tree_after_cleanup: Optional[str] = None
    drain_completed: bool = True
    drain_timed_out: bool = False
    drain_error: Optional[str] = None
    stdout: bytes = b""
    stderr: bytes = b""
    stdout_text: str = ""
    stderr_text: str = ""
    thread_id: Optional[str] = None
    turn_id: Optional[str] = None
    sidecar_process_status: str = "not_started"
    sdk_transport_status: str = "not_classified"
    inner_codex_command_runner_status: str = "not_classified"
    nexus_command_execution_status: str = "not_classified"
    final_result_candidate_status: str = "not_classified"


class CodexSdkBridgeClient:
    def __init__(self, config: CodexSdkBridgeClientConfig):
        self.config = config

    def run(self, request: CodexSessionRunRequest) -> CodexSdkBridgeResult:
        command = [self.config.node_path, self.config.sidecar_path, "--stdio"]
        payload = json.dumps(_request_payload(request, self.config), sort_keys=True).encode("utf-8")
        started_at = _utc_now()
        start_perf = time.perf_counter()
        process = subprocess.Popen(
            command,
            cwd=self.config.bounded_workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(payload, timeout=self.config.timeout_seconds)
            ended_at = _utc_now()
            result = _build_result(
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                command=command,
                pid=process.pid,
                started_at=started_at,
                ended_at=ended_at,
                elapsed_seconds=round(time.perf_counter() - start_perf, 6),
                timeout_seconds=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            timeout_at = _utc_now()
            process_tree_before = _process_tree_snapshot(process.pid)
            cleanup_started_at = _utc_now()
            cleanup = _kill_process_tree_result(process.pid)
            cleanup_ended_at = _utc_now()
            drain_completed = True
            drain_timed_out = False
            drain_error = None
            try:
                stdout, stderr = process.communicate(timeout=self.config.post_cleanup_timeout_seconds)
            except subprocess.TimeoutExpired as drain_exc:
                stdout = _timeout_stdout(drain_exc)
                stderr = _timeout_stderr(drain_exc)
                drain_completed = False
                drain_timed_out = True
                drain_error = "CODEX_SDK_POST_CLEANUP_DRAIN_TIMEOUT"
            ended_at = _utc_now()
            result = _build_result(
                exit_code=None,
                stdout=_timeout_stdout(exc) + (stdout or b""),
                stderr=_timeout_stderr(exc) + (stderr or b""),
                command=command,
                pid=process.pid,
                started_at=started_at,
                ended_at=ended_at,
                elapsed_seconds=round(time.perf_counter() - start_perf, 6),
                timeout_seconds=self.config.timeout_seconds,
                timed_out=True,
                error_code="CODEX_SDK_SIDECAR_TIMEOUT",
                timeout_at=timeout_at,
                cleanup_started_at=cleanup_started_at,
                cleanup_ended_at=cleanup_ended_at,
                post_cleanup_timeout_seconds=self.config.post_cleanup_timeout_seconds,
                cleanup_proven=cleanup["cleanup_proven"],
                cleanup_command=cleanup["command"],
                cleanup_exit_code=cleanup["exit_code"],
                cleanup_stdout=cleanup["stdout"],
                cleanup_stderr=cleanup["stderr"],
                process_tree_before_cleanup=process_tree_before,
                process_tree_after_cleanup=_process_tree_snapshot(process.pid),
                drain_completed=drain_completed,
                drain_timed_out=drain_timed_out,
                drain_error=drain_error,
            )
        if result.exit_code not in (0, None) and not result.error_code:
            result.error_code = "CODEX_SDK_SIDECAR_NONZERO_EXIT"
            result.errors.append(result.error_code)
        if self.config.evidence_root:
            result.evidence_refs = _dedupe(result.evidence_refs + _persist_sdk_bridge_evidence(self.config, request, result))
        return result


def _request_payload(request: CodexSessionRunRequest, config: CodexSdkBridgeClientConfig) -> dict[str, Any]:
    payload = {
        "schema_version": "4.19.codex.sdk_bridge_request.v1",
        "sidecar_protocol_version": config.sidecar_protocol_version,
        "run_id": request.run_id,
        "assignment_id": request.assignment_id,
        "task_id": request.task_id,
        "runtime_instance_id": request.runtime_instance_id,
        "workspace_ref": request.workspace_ref,
        "repo_ref": request.repo_ref,
        "bounded_workdir": config.bounded_workdir,
        "evidence_root": config.evidence_root,
        "timeout_ms": config.timeout_seconds * 1000,
        "allowed_write_surfaces": list(request.allowed_write_surfaces),
        "allowed_tools": list(request.allowed_tools),
        "required_commands": list(request.required_commands),
        "evidence_requirements": list(request.evidence_requirements),
        "no_go_scope": list(request.no_go_scope),
        "not_business_completion": request.not_business_completion,
        "live_sdk_authorized": config.live_sdk_authorized,
        "reviewed_codex_cli_versions": list(config.reviewed_codex_cli_versions),
        "reviewed_codex_cli_paths": list(config.reviewed_codex_cli_paths),
    }
    if config.codex_path_override:
        payload["codex_path_override"] = config.codex_path_override
    if config.prompt_contract:
        payload["prompt_contract"] = config.prompt_contract
    return payload


def _build_result(
    *,
    exit_code: Optional[int],
    stdout: bytes,
    stderr: bytes,
    command: list[str],
    pid: int,
    started_at: str,
    ended_at: str,
    elapsed_seconds: float,
    timeout_seconds: int,
    timed_out: bool = False,
    error_code: Optional[str] = None,
    timeout_at: Optional[str] = None,
    cleanup_started_at: Optional[str] = None,
    cleanup_ended_at: Optional[str] = None,
    post_cleanup_timeout_seconds: Optional[int] = None,
    cleanup_proven: bool = False,
    cleanup_command: Optional[list[str]] = None,
    cleanup_exit_code: Optional[int] = None,
    cleanup_stdout: bytes = b"",
    cleanup_stderr: bytes = b"",
    process_tree_before_cleanup: Optional[str] = None,
    process_tree_after_cleanup: Optional[str] = None,
    drain_completed: bool = True,
    drain_timed_out: bool = False,
    drain_error: Optional[str] = None,
) -> CodexSdkBridgeResult:
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    events, parse_errors = _parse_jsonl_events(stdout_text)
    final_result = _final_result(events)
    final_result_error_code = final_result.get("error_code") if isinstance(final_result.get("error_code"), str) else None
    thread_id = _first_value(events, "thread_id") or final_result.get("thread_id")
    turn_id = _first_value(events, "turn_id") or final_result.get("turn_id")
    errors = list(parse_errors)
    effective_error_code = error_code or final_result_error_code
    if effective_error_code:
        errors.append(effective_error_code)
    evidence_refs = ["sdk-bridge://events/jsonl"]
    if stderr:
        evidence_refs.append("sdk-bridge://stderr")
    if final_result:
        evidence_refs.append("sdk-bridge://result")
    if timed_out:
        evidence_refs.append("sdk-bridge://timeout/envelope")
    return CodexSdkBridgeResult(
        exit_code=exit_code,
        events=events,
        final_result=final_result,
        evidence_refs=_dedupe(evidence_refs),
        errors=_dedupe(errors),
        error_code=effective_error_code,
        timed_out=timed_out,
        pid=pid,
        command=list(command),
        started_at=started_at,
        timeout_at=timeout_at,
        cleanup_started_at=cleanup_started_at,
        cleanup_ended_at=cleanup_ended_at,
        ended_at=ended_at,
        elapsed_seconds=elapsed_seconds,
        timeout_seconds=timeout_seconds,
        post_cleanup_timeout_seconds=post_cleanup_timeout_seconds,
        cleanup_proven=cleanup_proven,
        cleanup_command=list(cleanup_command or []),
        cleanup_exit_code=cleanup_exit_code,
        cleanup_stdout=cleanup_stdout,
        cleanup_stderr=cleanup_stderr,
        process_tree_before_cleanup=process_tree_before_cleanup,
        process_tree_after_cleanup=process_tree_after_cleanup,
        drain_completed=drain_completed,
        drain_timed_out=drain_timed_out,
        drain_error=drain_error,
        stdout=stdout,
        stderr=stderr,
        stdout_text=stdout_text,
        stderr_text=stderr_text,
        thread_id=thread_id,
        turn_id=turn_id,
        sidecar_process_status=_sidecar_process_status(exit_code=exit_code, timed_out=timed_out, error_code=error_code),
        sdk_transport_status=_string_value(final_result, "sdk_transport_status") or _string_value(final_result, "status") or "not_classified",
        inner_codex_command_runner_status=_string_value(final_result, "inner_codex_command_runner_status") or "not_classified",
        nexus_command_execution_status=_string_value(final_result, "nexus_command_execution_status") or "not_classified",
        final_result_candidate_status=_string_value(final_result, "final_result_candidate_status") or _string_value(final_result, "status") or "not_classified",
    )


def _parse_jsonl_events(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append("CODEX_SDK_SIDECAR_NON_JSON_STDOUT")
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            errors.append("CODEX_SDK_SIDECAR_UNSUPPORTED_EVENT")
    return events, errors


def _final_result(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("type") == "result":
            return dict(event)
    return {}


def _first_value(events: list[dict[str, Any]], key: str) -> Optional[str]:
    for event in events:
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _string_value(payload: dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _sidecar_process_status(*, exit_code: Optional[int], timed_out: bool, error_code: Optional[str]) -> str:
    if timed_out:
        return "timeout"
    if error_code in {"CODEX_SDK_SIDECAR_SUBPROCESS_NOT_FOUND", "CODEX_SDK_SIDECAR_SUBPROCESS_ERROR"}:
        return "failed_to_start"
    if exit_code == 0:
        return "exited_zero"
    if exit_code is None:
        return "not_available"
    return "exited_nonzero"


def _persist_sdk_bridge_evidence(
    config: CodexSdkBridgeClientConfig,
    request: CodexSessionRunRequest,
    result: CodexSdkBridgeResult,
) -> list[str]:
    root = Path(config.evidence_root or "")
    root.mkdir(parents=True, exist_ok=True)
    stdout_text, stdout_truncated = _stream_excerpt(result.stdout, config.stream_excerpt_bytes)
    stderr_text, stderr_truncated = _stream_excerpt(result.stderr, config.stream_excerpt_bytes)
    _write_text(root / "sidecar_stdout.jsonl", stdout_text)
    _write_text(root / "sidecar_stderr.txt", stderr_text)
    _write_text(root / "sdk_events.jsonl", "\n".join(json.dumps(event, sort_keys=True) for event in result.events))
    _write_text(root / "final_result.json", json.dumps(result.final_result, indent=2, sort_keys=True))
    envelope = {
        "run_id": request.run_id,
        "assignment_id": request.assignment_id,
        "task_id": request.task_id,
        "runtime_instance_id": request.runtime_instance_id,
        "command": _redact_command(result.command),
        "pid": result.pid,
        "exit_code": result.exit_code,
        "error_code": result.error_code,
        "timed_out": result.timed_out,
        "sidecar_process_status": result.sidecar_process_status,
        "sdk_transport_status": result.sdk_transport_status,
        "inner_codex_command_runner_status": result.inner_codex_command_runner_status,
        "nexus_command_execution_status": result.nexus_command_execution_status,
        "final_result_candidate_status": result.final_result_candidate_status,
        "started_at": result.started_at,
        "timeout_at": result.timeout_at,
        "cleanup_started_at": result.cleanup_started_at,
        "cleanup_ended_at": result.cleanup_ended_at,
        "ended_at": result.ended_at,
        "elapsed_seconds": result.elapsed_seconds,
        "timeout_seconds": result.timeout_seconds,
        "thread_id": result.thread_id,
        "turn_id": result.turn_id,
        "streams": {
            "stdout_ref": "sidecar_stdout.jsonl",
            "stderr_ref": "sidecar_stderr.txt",
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
        },
        "cleanup": {
            "command": result.cleanup_command,
            "exit_code": result.cleanup_exit_code,
            "cleanup_proven": result.cleanup_proven,
            "stdout": _redact_text(result.cleanup_stdout.decode("utf-8", errors="replace")),
            "stderr": _redact_text(result.cleanup_stderr.decode("utf-8", errors="replace")),
        },
        "drain": {
            "completed": result.drain_completed,
            "timed_out": result.drain_timed_out,
            "error": result.drain_error,
            "post_cleanup_timeout_seconds": result.post_cleanup_timeout_seconds,
        },
    }
    _write_text(root / "sdk_bridge_envelope.json", json.dumps(envelope, indent=2, sort_keys=True))
    return [
        "sdk-bridge://evidence/envelope",
        "sdk-bridge://events/jsonl",
        "sdk-bridge://stdout",
        "sdk-bridge://stderr",
    ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped
