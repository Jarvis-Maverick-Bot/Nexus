"""Codex session runner abstraction for WBS 7.19.13.

This module intentionally provides a disabled runner only. It does not launch
Codex, start a daemon, or connect to live transport.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from nexus.mq.agent_registry_events import secret_material_errors


CODEX_SESSION_RUN_REQUEST_SCHEMA_VERSION = "4.19.codex.session_run_request.v1"


@dataclass
class CodexSessionValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class CodexSessionRunRequest:
    run_id: str
    assignment_id: str
    task_id: str
    runtime_instance_id: str
    workspace_ref: str
    repo_ref: str
    allowed_write_surfaces: list[str]
    allowed_tools: list[str]
    required_commands: list[str]
    evidence_requirements: list[str]
    no_go_scope: list[str]
    started_at: str
    schema_version: str = CODEX_SESSION_RUN_REQUEST_SCHEMA_VERSION
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodexSessionRunnerResult:
    status: str
    evidence_refs: list[str]
    errors: list[str] = field(default_factory=list)
    live_execution_started: bool = False
    not_business_completion: bool = True
    started: bool = False
    exit_code: Optional[int] = None
    error_code: Optional[str] = None
    changed_file_refs: list[str] = field(default_factory=list)
    disallowed_write_refs: list[str] = field(default_factory=list)
    no_go_refs: list[str] = field(default_factory=list)
    cleanup_refs: list[str] = field(default_factory=list)
    drain_refs: list[str] = field(default_factory=list)
    offline_refs: list[str] = field(default_factory=list)
    result_candidate_ref: Optional[str] = None


class CodexSessionRunner(Protocol):
    def run(self, request: CodexSessionRunRequest) -> CodexSessionRunnerResult:
        ...


class DisabledCodexSessionRunner:
    def run(self, request: CodexSessionRunRequest) -> CodexSessionRunnerResult:
        validation = validate_codex_session_run_request(request)
        errors = list(validation.errors)
        errors.append("CODEX_SESSION_RUNNER_DISABLED")
        return CodexSessionRunnerResult(
            status="blocked",
            evidence_refs=[],
            errors=_dedupe(errors),
            live_execution_started=False,
        )


@dataclass
class CodexCliRunnerConfig:
    cli_path: Optional[str] = None
    bounded_workdir: Optional[str] = None
    timeout_seconds: int = 120
    appdata_bin_root: Optional[str] = None
    prohibited_write_surfaces: list[str] = field(default_factory=list)


@dataclass
class CodexCliPathProbeResult:
    path: str
    version: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors and bool(self.version)


@dataclass
class CodexCliPathSelectionResult:
    selected_path: Optional[str]
    selected_version: Optional[str]
    probed_candidates: list[CodexCliPathProbeResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CodexCliProcessResult:
    exit_code: Optional[int]
    stdout: bytes
    stderr: bytes
    timed_out: bool = False
    cleanup_proven: bool = False


@dataclass
class CodexCliGitStatusSnapshot:
    changed_file_refs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CodexStdoutFilterResult:
    events: list[dict[str, Any]]
    non_json_stdout: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CodexCliProcessRunner(Protocol):
    def __call__(self, command: list[str], *, cwd: str, timeout_seconds: int) -> CodexCliProcessResult:
        ...


CodexCliProbe = Callable[[str], CodexCliPathProbeResult]
CodexCliGitStatusReader = Callable[[str], CodexCliGitStatusSnapshot]


class CliCodexSessionRunner:
    def __init__(
        self,
        *,
        config: CodexCliRunnerConfig,
        probe: Optional[CodexCliProbe] = None,
        process_runner: Optional[CodexCliProcessRunner] = None,
        git_status_reader: Optional[CodexCliGitStatusReader] = None,
    ):
        self.config = config
        self.probe = probe or probe_codex_cli_path
        self.process_runner = process_runner or run_codex_cli_process
        self.git_status_reader = git_status_reader or read_git_status_snapshot
        self._assignment_results: dict[str, tuple[str, CodexSessionRunnerResult]] = {}

    def run(self, request: CodexSessionRunRequest) -> CodexSessionRunnerResult:
        validation = validate_codex_session_run_request(request)
        if not validation.valid:
            return CodexSessionRunnerResult(
                status="blocked",
                evidence_refs=[],
                errors=validation.errors,
                live_execution_started=False,
            )
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
                replay.evidence_refs = _dedupe(replay.evidence_refs + ["codex-cli://duplicate/replay-suppressed"])
                return replay
            return _blocked_result(
                request,
                error_code="CODEX_DUPLICATE_SUPPRESSED",
                evidence_refs=["codex-cli://duplicate/suppressed-conflict"],
            )

        if not self.config.bounded_workdir:
            return CodexSessionRunnerResult(
                status="blocked",
                evidence_refs=[],
                errors=["CODEX_CLI_BOUNDED_WORKDIR_REQUIRED"],
                live_execution_started=False,
                error_code="CODEX_CLI_BOUNDED_WORKDIR_REQUIRED",
                result_candidate_ref=_result_candidate_ref(request, "blocked"),
            )

        pre_status = self.git_status_reader(self.config.bounded_workdir)
        if pre_status.errors:
            result = _blocked_result(
                request,
                error_code=pre_status.errors[0],
                evidence_refs=["codex-cli://git-status/pre/unavailable"],
            )
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result
        if pre_status.changed_file_refs:
            result = _blocked_result(
                request,
                error_code="CODEX_DIRTY_WORKTREE",
                evidence_refs=["codex-cli://git-status/pre/dirty"],
                changed_file_refs=pre_status.changed_file_refs,
            )
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result

        selection = select_codex_cli_path(
            config=self.config,
            discovered_candidates=discover_appdata_codex_cli_candidates(self.config),
            probe=self.probe,
        )
        if not selection.selected_path:
            result = _blocked_result(
                request,
                error_code=(selection.errors or ["CODEX_CLI_NOT_CONFIGURED"])[0],
                evidence_refs=_selection_evidence_refs(selection),
            )
            self._assignment_results[request.assignment_id] = (fingerprint, result)
            return result

        command = _build_codex_exec_command(selection.selected_path, request, self.config.bounded_workdir)
        process = self.process_runner(
            command,
            cwd=self.config.bounded_workdir,
            timeout_seconds=self.config.timeout_seconds,
        )
        post_status = self.git_status_reader(self.config.bounded_workdir)
        stdout = filter_codex_stdout_events(process.stdout)
        evidence_refs = _selection_evidence_refs(selection)
        evidence_refs.append(f"codex-cli://stdout/events/{len(stdout.events)}")
        if stdout.non_json_stdout:
            evidence_refs.append(f"codex-cli://stdout/non-json/{len(stdout.non_json_stdout)}")
        if process.stderr:
            evidence_refs.append("codex-cli://stderr/captured")
        cleanup_refs: list[str] = []
        if process.cleanup_proven:
            cleanup_refs.append("codex-cli://process/cleanup-proven")
            evidence_refs.extend(cleanup_refs)

        errors = list(stdout.errors)
        status = "completed_execution"
        if process.timed_out:
            errors.append("CODEX_CLI_TIMEOUT")
        elif process.exit_code != 0:
            errors.append("CODEX_CLI_NONZERO_EXIT")
        changed_file_refs = list(post_status.changed_file_refs)
        disallowed_write_refs = _disallowed_write_refs(changed_file_refs, request.allowed_write_surfaces)
        no_go_refs = _matching_write_refs(changed_file_refs, self.config.prohibited_write_surfaces)
        drain_refs: list[str] = []
        offline_refs: list[str] = []
        if post_status.errors:
            errors.extend(post_status.errors)
            status = "quarantined"
            drain_refs.append("codex-cli://drain/git-status-unavailable")
            evidence_refs.append("codex-cli://git-status/post/unavailable")
            evidence_refs.extend(drain_refs)
        elif no_go_refs:
            errors.append("CODEX_NO_GO_SCOPE_VIOLATION")
            status = "quarantined"
            offline_refs.append("codex-cli://offline/no-go-scope-violation")
            evidence_refs.extend(offline_refs)
        elif disallowed_write_refs:
            errors.append("CODEX_WRITE_SURFACE_VIOLATION")
            status = "quarantined"
            drain_refs.append("codex-cli://drain/write-surface-violation")
            evidence_refs.extend(drain_refs)
        if errors:
            if status != "quarantined":
                status = "blocked"
        result = CodexSessionRunnerResult(
            status=status,
            evidence_refs=_dedupe(evidence_refs),
            errors=_dedupe(errors),
            live_execution_started=False,
            started=True,
            exit_code=process.exit_code,
            error_code=_dedupe(errors)[0] if errors else None,
            changed_file_refs=changed_file_refs,
            disallowed_write_refs=disallowed_write_refs,
            no_go_refs=no_go_refs,
            cleanup_refs=cleanup_refs,
            drain_refs=drain_refs,
            offline_refs=offline_refs,
            result_candidate_ref=_result_candidate_ref(request, status),
        )
        self._assignment_results[request.assignment_id] = (fingerprint, result)
        return result


def validate_codex_session_run_request(request: CodexSessionRunRequest) -> CodexSessionValidationResult:
    errors: list[str] = []
    if request.schema_version != CODEX_SESSION_RUN_REQUEST_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_CODEX_SESSION_RUN_REQUEST_SCHEMA")
    if request.not_business_completion is not True:
        errors.append("CODEX_SESSION_RUN_REQUEST_CANNOT_BE_BUSINESS_COMPLETION")
    for field_name in (
        "run_id",
        "assignment_id",
        "task_id",
        "runtime_instance_id",
        "workspace_ref",
        "repo_ref",
        "allowed_write_surfaces",
        "allowed_tools",
        "required_commands",
        "evidence_requirements",
        "no_go_scope",
        "started_at",
    ):
        if not getattr(request, field_name):
            errors.append(f"MISSING_CODEX_SESSION_RUN_FIELD: {field_name}")
    errors.extend(secret_material_errors(request.to_dict(), path="codex_session_run_request"))
    return CodexSessionValidationResult(valid=not errors, errors=_dedupe(errors))


def select_codex_cli_path(
    *,
    config: CodexCliRunnerConfig,
    discovered_candidates: list[str],
    probe: CodexCliProbe,
) -> CodexCliPathSelectionResult:
    if config.cli_path:
        probed = probe(config.cli_path)
        if probed.passed:
            return CodexCliPathSelectionResult(probed.path, probed.version, [probed], [])
        return CodexCliPathSelectionResult(
            None,
            None,
            [probed],
            _dedupe(probed.errors or ["CODEX_CLI_CONTRACT_UNPROVEN"]),
        )

    probes = [probe(path) for path in discovered_candidates]
    passing = [result for result in probes if result.passed]
    if passing:
        sorted_passing = sorted(passing, key=lambda result: _version_sort_key(result.version), reverse=True)
        selected = sorted_passing[0]
        selected_key = _version_sort_key(selected.version)
        if sum(1 for result in sorted_passing if _version_sort_key(result.version) == selected_key) > 1:
            return CodexCliPathSelectionResult(None, None, probes, ["CODEX_CLI_AMBIGUOUS_CANDIDATES"])
        return CodexCliPathSelectionResult(selected.path, selected.version, probes, [])
    errors: list[str] = []
    for result in probes:
        errors.extend(result.errors)
    return CodexCliPathSelectionResult(None, None, probes, _dedupe(errors or ["CODEX_CLI_NOT_CONFIGURED"]))


def discover_appdata_codex_cli_candidates(config: CodexCliRunnerConfig) -> list[str]:
    root = config.appdata_bin_root
    if root is None:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if not local_appdata:
            return []
        root = os.path.join(local_appdata, "OpenAI", "Codex", "bin")
    base = Path(root)
    if not base.exists():
        return []
    candidates = [str(path) for path in base.rglob("codex.exe") if path.is_file()]
    return sorted(candidates)


def probe_codex_cli_path(path: str) -> CodexCliPathProbeResult:
    version, version_error = _run_cli_probe_command([path, "--version"])
    if version_error:
        return CodexCliPathProbeResult(path=path, errors=[version_error])
    if version.returncode != 0:
        return CodexCliPathProbeResult(path=path, errors=["CODEX_CLI_VERSION_FAILED"])
    errors: list[str] = []
    help_result, help_error = _run_cli_probe_command([path, "--help"])
    if help_error:
        errors.append(help_error)
        return CodexCliPathProbeResult(path=path, version=_decode_process_bytes(version.stdout).strip(), errors=_dedupe(errors))
    exec_help, exec_help_error = _run_cli_probe_command([path, "exec", "--help"])
    if exec_help_error:
        errors.append(exec_help_error)
        return CodexCliPathProbeResult(path=path, version=_decode_process_bytes(version.stdout).strip(), errors=_dedupe(errors))
    if help_result.returncode != 0:
        errors.append("CODEX_CLI_HELP_FAILED")
    if exec_help.returncode != 0:
        errors.append("CODEX_CLI_EXEC_HELP_FAILED")
    decoded_version = _decode_process_bytes(version.stdout).strip()
    return CodexCliPathProbeResult(path=path, version=decoded_version, errors=errors)


def read_git_status_snapshot(cwd: str) -> CodexCliGitStatusSnapshot:
    try:
        completed = subprocess.run(
            ["git", "-C", cwd, "status", "--short", "--untracked-files=all"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CodexCliGitStatusSnapshot(errors=["CODEX_GIT_STATUS_TIMEOUT"])
    except OSError:
        return CodexCliGitStatusSnapshot(errors=["CODEX_GIT_STATUS_OS_ERROR"])
    if completed.returncode != 0:
        return CodexCliGitStatusSnapshot(errors=["CODEX_GIT_STATUS_NONZERO_EXIT"])
    return CodexCliGitStatusSnapshot(changed_file_refs=_parse_git_status_paths(_decode_process_bytes(completed.stdout)))


def run_codex_cli_process(command: list[str], *, cwd: str, timeout_seconds: int) -> CodexCliProcessResult:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return CodexCliProcessResult(
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            cleanup_proven=True,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup_proven = _kill_process_tree(process.pid)
        stdout, stderr = process.communicate()
        return CodexCliProcessResult(
            exit_code=None,
            stdout=(exc.stdout or b"") + (stdout or b""),
            stderr=(exc.stderr or b"") + (stderr or b""),
            timed_out=True,
            cleanup_proven=cleanup_proven,
        )


def filter_codex_stdout_events(stdout: bytes) -> CodexStdoutFilterResult:
    text = _decode_process_bytes(stdout)
    events: list[dict[str, Any]] = []
    non_json_stdout: list[str] = []
    errors: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.lstrip("\ufeff")
        if not line.startswith("{"):
            non_json_stdout.append(line)
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            errors.append("CODEX_CLI_STDOUT_INVALID_JSON")
    return CodexStdoutFilterResult(events=events, non_json_stdout=non_json_stdout, errors=_dedupe(errors))


def _build_codex_exec_command(path: str, request: CodexSessionRunRequest, bounded_workdir: str) -> list[str]:
    prompt = (
        "Execute this bounded non-business Codex assignment. "
        f"run_id={request.run_id}; assignment_id={request.assignment_id}; task_id={request.task_id}. "
        "Preserve no-go boundaries and emit result_candidate evidence only."
    )
    return [
        path,
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "-C",
        bounded_workdir,
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-rules",
        prompt,
    ]


def _selection_evidence_refs(selection: CodexCliPathSelectionResult) -> list[str]:
    refs: list[str] = []
    for result in selection.probed_candidates:
        if result.version:
            refs.append(f"codex-cli://{result.path}@{result.version}")
        for error in result.errors:
            refs.append(f"codex-cli://{result.path}/{error}")
    return refs


def _run_cli_probe_command(command: list[str]) -> tuple[Optional[subprocess.CompletedProcess], Optional[str]]:
    try:
        return subprocess.run(command, capture_output=True, timeout=10, check=False), None
    except subprocess.TimeoutExpired:
        return None, "CODEX_CLI_PROBE_TIMEOUT"
    except PermissionError:
        return None, "CODEX_CLI_ACCESS_DENIED"
    except OSError:
        return None, "CODEX_CLI_NOT_FOUND"


def _decode_process_bytes(data: bytes) -> str:
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _parse_git_status_paths(status_output: str) -> list[str]:
    paths: list[str] = []
    for line in status_output.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(_normalize_ref(path.strip()))
    return paths


def _disallowed_write_refs(changed_file_refs: list[str], allowed_write_surfaces: list[str]) -> list[str]:
    return [
        ref
        for ref in changed_file_refs
        if not _matches_any(ref, allowed_write_surfaces)
    ]


def _matching_write_refs(changed_file_refs: list[str], write_surfaces: list[str]) -> list[str]:
    return [ref for ref in changed_file_refs if _matches_any(ref, write_surfaces)]


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = _normalize_ref(path)
    return any(fnmatch.fnmatch(normalized, _normalize_ref(pattern)) for pattern in patterns)


def _normalize_ref(path: str) -> str:
    return path.replace("\\", "/")


def _request_fingerprint(request: CodexSessionRunRequest) -> str:
    payload = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result_candidate_ref(request: CodexSessionRunRequest, status: str) -> str:
    return f"codex-result-candidate://{request.run_id}/{request.assignment_id}/{status}"


def _blocked_result(
    request: CodexSessionRunRequest,
    *,
    error_code: str,
    evidence_refs: Optional[list[str]] = None,
    changed_file_refs: Optional[list[str]] = None,
) -> CodexSessionRunnerResult:
    return CodexSessionRunnerResult(
        status="blocked",
        evidence_refs=evidence_refs or [],
        errors=[error_code],
        live_execution_started=False,
        started=False,
        error_code=error_code,
        changed_file_refs=changed_file_refs or [],
        result_candidate_ref=_result_candidate_ref(request, "blocked"),
    )


def _copy_result(result: CodexSessionRunnerResult) -> CodexSessionRunnerResult:
    return CodexSessionRunnerResult(
        status=result.status,
        evidence_refs=list(result.evidence_refs),
        errors=list(result.errors),
        live_execution_started=result.live_execution_started,
        not_business_completion=result.not_business_completion,
        started=result.started,
        exit_code=result.exit_code,
        error_code=result.error_code,
        changed_file_refs=list(result.changed_file_refs),
        disallowed_write_refs=list(result.disallowed_write_refs),
        no_go_refs=list(result.no_go_refs),
        cleanup_refs=list(result.cleanup_refs),
        drain_refs=list(result.drain_refs),
        offline_refs=list(result.offline_refs),
        result_candidate_ref=result.result_candidate_ref,
    )


def _kill_process_tree(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return completed.returncode == 0
    try:
        os.kill(pid, 9)
        return True
    except OSError:
        return False


def _version_sort_key(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return tuple()
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return tuple()
    return tuple(int(part) for part in match.groups())


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
