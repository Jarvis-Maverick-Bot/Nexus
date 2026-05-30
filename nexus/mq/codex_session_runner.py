"""Codex session runner abstraction for WBS 7.19.13.

This module intentionally provides a disabled runner only. It does not launch
Codex, start a daemon, or connect to live transport.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

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


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error and error not in deduped:
            deduped.append(error)
    return deduped
