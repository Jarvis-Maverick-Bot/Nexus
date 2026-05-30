"""Codex session runner abstraction for WBS 7.19.13.

This module intentionally provides a disabled runner only. It does not launch
Codex, start a daemon, or connect to live transport.
"""

from __future__ import annotations

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
class CodexStdoutFilterResult:
    events: list[dict[str, Any]]
    non_json_stdout: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class CodexCliProcessRunner(Protocol):
    def __call__(self, command: list[str], *, cwd: str, timeout_seconds: int) -> CodexCliProcessResult:
        ...


CodexCliProbe = Callable[[str], CodexCliPathProbeResult]


class CliCodexSessionRunner:
    def __init__(
        self,
        *,
        config: CodexCliRunnerConfig,
        probe: Optional[CodexCliProbe] = None,
        process_runner: Optional[CodexCliProcessRunner] = None,
    ):
        self.config = config
        self.probe = probe or probe_codex_cli_path
        self.process_runner = process_runner or run_codex_cli_process

    def run(self, request: CodexSessionRunRequest) -> CodexSessionRunnerResult:
        validation = validate_codex_session_run_request(request)
        if not validation.valid:
            return CodexSessionRunnerResult(
                status="blocked",
                evidence_refs=[],
                errors=validation.errors,
                live_execution_started=False,
            )
        if not self.config.bounded_workdir:
            return CodexSessionRunnerResult(
                status="blocked",
                evidence_refs=[],
                errors=["CODEX_CLI_BOUNDED_WORKDIR_REQUIRED"],
                live_execution_started=False,
            )

        selection = select_codex_cli_path(
            config=self.config,
            discovered_candidates=discover_appdata_codex_cli_candidates(self.config),
            probe=self.probe,
        )
        if not selection.selected_path:
            return CodexSessionRunnerResult(
                status="blocked",
                evidence_refs=_selection_evidence_refs(selection),
                errors=selection.errors or ["CODEX_CLI_NOT_CONFIGURED"],
                live_execution_started=False,
            )

        command = _build_codex_exec_command(selection.selected_path, request, self.config.bounded_workdir)
        process = self.process_runner(
            command,
            cwd=self.config.bounded_workdir,
            timeout_seconds=self.config.timeout_seconds,
        )
        stdout = filter_codex_stdout_events(process.stdout)
        evidence_refs = _selection_evidence_refs(selection)
        evidence_refs.append(f"codex-cli://stdout/events/{len(stdout.events)}")
        if stdout.non_json_stdout:
            evidence_refs.append(f"codex-cli://stdout/non-json/{len(stdout.non_json_stdout)}")
        if process.stderr:
            evidence_refs.append("codex-cli://stderr/captured")
        if process.cleanup_proven:
            evidence_refs.append("codex-cli://process/cleanup-proven")

        errors = list(stdout.errors)
        status = "completed_execution"
        if process.timed_out:
            errors.append("CODEX_CLI_TIMEOUT")
        elif process.exit_code != 0:
            errors.append("CODEX_CLI_NONZERO_EXIT")
        if errors:
            status = "blocked"
        return CodexSessionRunnerResult(
            status=status,
            evidence_refs=_dedupe(evidence_refs),
            errors=_dedupe(errors),
            live_execution_started=False,
        )


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
    try:
        version = subprocess.run([path, "--version"], capture_output=True, timeout=10, check=False)
    except PermissionError:
        return CodexCliPathProbeResult(path=path, errors=["CODEX_CLI_ACCESS_DENIED"])
    except OSError:
        return CodexCliPathProbeResult(path=path, errors=["CODEX_CLI_NOT_FOUND"])
    if version.returncode != 0:
        return CodexCliPathProbeResult(path=path, errors=["CODEX_CLI_VERSION_FAILED"])
    help_result = subprocess.run([path, "--help"], capture_output=True, timeout=10, check=False)
    exec_help = subprocess.run([path, "exec", "--help"], capture_output=True, timeout=10, check=False)
    errors: list[str] = []
    if help_result.returncode != 0:
        errors.append("CODEX_CLI_HELP_FAILED")
    if exec_help.returncode != 0:
        errors.append("CODEX_CLI_EXEC_HELP_FAILED")
    decoded_version = _decode_process_bytes(version.stdout).strip()
    return CodexCliPathProbeResult(path=path, version=decoded_version, errors=errors)


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


def _decode_process_bytes(data: bytes) -> str:
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


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
