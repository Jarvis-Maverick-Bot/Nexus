"""Primary Codex SDK session runner adapter for WBS 7.19.13."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from nexus.mq.codex_sdk_bridge_client import CodexSdkBridgeClient, CodexSdkBridgeClientConfig, CodexSdkBridgeResult
from nexus.mq.codex_session_runner import (
    CodexCliGitStatusReader,
    CodexCliGitStatusSnapshot,
    CodexSessionRunRequest,
    CodexSessionRunnerResult,
    _copy_result,
    _dedupe,
    _disallowed_write_refs,
    _matching_write_refs,
    _result_candidate_ref,
    read_git_status_snapshot,
    validate_codex_session_run_request,
)


@dataclass
class CodexSdkRunnerConfig:
    bounded_workdir: Optional[str] = None
    prohibited_write_surfaces: list[str] = field(default_factory=list)


CodexSdkBridgeRunner = Callable[[CodexSessionRunRequest], CodexSdkBridgeResult]


class SdkCodexSessionRunner:
    def __init__(
        self,
        *,
        config: CodexSdkRunnerConfig,
        bridge_runner: Optional[CodexSdkBridgeRunner] = None,
        bridge_client_config: Optional[CodexSdkBridgeClientConfig] = None,
        git_status_reader: Optional[CodexCliGitStatusReader] = None,
    ):
        self.config = config
        if bridge_runner is None:
            if bridge_client_config is None:
                raise ValueError("CODEX_SDK_BRIDGE_CLIENT_CONFIG_REQUIRED")
            bridge_runner = CodexSdkBridgeClient(bridge_client_config).run
        self.bridge_runner = bridge_runner
        self.git_status_reader = git_status_reader or read_git_status_snapshot
        self._assignment_results: dict[str, tuple[str, CodexSessionRunnerResult]] = {}

    def run(self, request: CodexSessionRunRequest) -> CodexSessionRunnerResult:
        validation = validate_codex_session_run_request(request)
        if not validation.valid:
            return CodexSessionRunnerResult(status="blocked", evidence_refs=[], errors=validation.errors)
        fingerprint = _request_fingerprint(request)
        previous = self._assignment_results.get(request.assignment_id)
        if previous:
            previous_fingerprint, previous_result = previous
            if previous_fingerprint == fingerprint:
                replay = _copy_result(previous_result)
                replay.status = "blocked"
                replay.started = False
                replay.errors = _dedupe(replay.errors + ["CODEX_DUPLICATE_SUPPRESSED"])
                replay.error_code = "CODEX_DUPLICATE_SUPPRESSED"
                replay.evidence_refs = _dedupe(replay.evidence_refs + ["sdk-bridge://duplicate/replay-suppressed"])
                return replay
            result = _blocked_result(request, "CODEX_DUPLICATE_SUPPRESSED", ["sdk-bridge://duplicate/suppressed-conflict"])
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result

        if not self.config.bounded_workdir:
            return _blocked_result(request, "CODEX_SDK_BOUNDED_WORKDIR_REQUIRED", [])

        pre_status = self.git_status_reader(self.config.bounded_workdir)
        if pre_status.errors:
            result = _blocked_result(request, pre_status.errors[0], ["sdk-bridge://git-status/pre/unavailable"])
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result
        if pre_status.changed_file_refs:
            result = _blocked_result(
                request,
                "CODEX_DIRTY_WORKTREE",
                ["sdk-bridge://git-status/pre/dirty"],
                changed_file_refs=pre_status.changed_file_refs,
            )
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result

        bridge = self.bridge_runner(request)
        post_status = self.git_status_reader(self.config.bounded_workdir)
        errors = list(bridge.errors)
        if bridge.error_code:
            errors.append(bridge.error_code)
        elif bridge.exit_code not in (0, None):
            errors.append("CODEX_SDK_SIDECAR_NONZERO_EXIT")
        changed_file_refs = list(post_status.changed_file_refs)
        disallowed_write_refs = _disallowed_write_refs(changed_file_refs, request.allowed_write_surfaces)
        no_go_refs = _matching_write_refs(changed_file_refs, self.config.prohibited_write_surfaces)
        evidence_refs = _dedupe(["sdk-bridge://runner/primary"] + bridge.evidence_refs)
        status = _bridge_status(bridge)
        drain_refs: list[str] = []
        offline_refs: list[str] = []
        if post_status.errors:
            errors.extend(post_status.errors)
            status = "quarantined"
            drain_refs.append("sdk-bridge://drain/git-status-unavailable")
            evidence_refs.extend(drain_refs)
        elif no_go_refs:
            errors.append("CODEX_NO_GO_SCOPE_VIOLATION")
            status = "quarantined"
            offline_refs.append("sdk-bridge://offline/no-go-scope-violation")
            evidence_refs.extend(offline_refs)
        elif disallowed_write_refs:
            errors.append("CODEX_WRITE_SURFACE_VIOLATION")
            status = "quarantined"
            drain_refs.append("sdk-bridge://drain/write-surface-violation")
            evidence_refs.extend(drain_refs)
        if errors and status != "quarantined":
            status = "blocked"
        result = CodexSessionRunnerResult(
            status=status,
            evidence_refs=_dedupe(evidence_refs),
            errors=_dedupe(errors),
            live_execution_started=False,
            started=True,
            exit_code=bridge.exit_code,
            error_code=_dedupe(errors)[0] if errors else None,
            changed_file_refs=changed_file_refs,
            disallowed_write_refs=disallowed_write_refs,
            no_go_refs=no_go_refs,
            drain_refs=drain_refs,
            offline_refs=offline_refs,
            result_candidate_ref=_result_candidate_ref(request, status),
        )
        self._assignment_results[request.assignment_id] = (fingerprint, result)
        return result


def _bridge_status(bridge: CodexSdkBridgeResult) -> str:
    status = bridge.final_result.get("status")
    if status in {"completed_execution", "blocked", "failed", "interrupted", "quarantined"}:
        return status
    if bridge.error_code or bridge.timed_out or bridge.exit_code not in (0, None):
        return "blocked"
    return "completed_execution"


def _request_fingerprint(request: CodexSessionRunRequest) -> str:
    payload = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _blocked_result(
    request: CodexSessionRunRequest,
    error_code: str,
    evidence_refs: list[str],
    *,
    changed_file_refs: Optional[list[str]] = None,
) -> CodexSessionRunnerResult:
    return CodexSessionRunnerResult(
        status="blocked",
        evidence_refs=evidence_refs,
        errors=[error_code],
        live_execution_started=False,
        started=False,
        error_code=error_code,
        changed_file_refs=changed_file_refs or [],
        result_candidate_ref=_result_candidate_ref(request, "blocked"),
    )
