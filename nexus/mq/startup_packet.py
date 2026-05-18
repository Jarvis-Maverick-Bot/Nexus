"""Startup packet validation for 4.19 agent readiness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class StartupPacketRecord:
    packet_id: str
    agent_id: str
    runtime_instance_id: str
    role_seat: str
    active_objective: str
    measurable_first_task: str
    live_decisions: list[str]
    deprecated_reference_only: list[str]
    no_go_scope: list[str]
    source_authority_refs: list[str]
    message_bus_access_expectations: dict[str, Any]
    current_project_state: str
    required_skills: list[str]
    required_memory_surfaces: list[str]
    evidence_requirements: list[str]
    reply_format_ref: str
    stop_conditions: list[str]
    issued_at: str
    supersedes_packet_id: Optional[str] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StartupPacketValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)


def validate_startup_packet(packet: StartupPacketRecord) -> StartupPacketValidationResult:
    errors: list[str] = []
    if not packet.active_objective:
        errors.append("MISSING_ACTIVE_OBJECTIVE")
    if not packet.measurable_first_task:
        errors.append("MISSING_FIRST_TASK")
    if not packet.message_bus_access_expectations:
        errors.append("MISSING_MESSAGE_BUS_ACCESS")
    if not packet.current_project_state:
        errors.append("MISSING_CURRENT_PROJECT_STATE")
    if not packet.no_go_scope:
        errors.append("MISSING_NO_GO_SCOPE")
    if not packet.source_authority_refs:
        errors.append("MISSING_SOURCE_AUTHORITY")
    if not packet.stop_conditions:
        errors.append("MISSING_STOP_CONDITIONS")
    return StartupPacketValidationResult(valid=not errors, errors=errors)


def verify_startup_packet_readiness(
    packet: StartupPacketRecord,
    *,
    readiness_evidence_refs: list[str],
) -> StartupPacketValidationResult:
    """Return readiness only when packet validation and external evidence pass."""
    result = validate_startup_packet(packet)
    errors = list(result.errors)
    if not readiness_evidence_refs:
        errors.append("MISSING_READINESS_EVIDENCE")
    if not packet.evidence_requirements:
        errors.append("MISSING_EVIDENCE_REQUIREMENTS")
    return StartupPacketValidationResult(
        valid=not errors,
        errors=_dedupe(errors),
        evidence_refs=list(readiness_evidence_refs),
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
