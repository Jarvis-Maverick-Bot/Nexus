"""Adapter-boundary candidate runtime registry helpers for WBS 7.18."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.agent_registry_store import AgentRegistryWriteResult
from nexus.mq.candidate_runtime_identity import (
    CandidateAgentProfile,
    CandidateRuntimeIdentity,
    build_candidate_registry_record,
    validate_candidate_runtime_identity,
)


@dataclass
class CandidateRuntimeRegistrationResult:
    accepted: bool
    record: Optional[AgentRegistryRecord] = None
    revision: Optional[int] = None
    errors: list[str] = field(default_factory=list)
    duplicate_suppressed: bool = False
    quarantined_existing: bool = False
    not_business_completion: bool = True


@dataclass
class CandidateRuntimeMigrationRequest:
    agent_id: str
    candidate_profile_ref: str
    source_runtime_instance_id: str
    target_runtime_instance_id: str
    owner_principal_id: str
    runtime_provider: str
    migration_id: str
    evidence_ref: str
    not_business_completion: bool = True


@dataclass
class CandidateRuntimeMigrationDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


class CandidateRuntimeRegistry:
    def __init__(self, registry_service: AgentRegistryService):
        self._registry_service = registry_service

    def register_or_refresh_candidate_runtime(
        self,
        *,
        profile: CandidateAgentProfile,
        identity: CandidateRuntimeIdentity,
        now_at: str,
        expected_revision: Optional[int] = None,
    ) -> CandidateRuntimeRegistrationResult:
        validation = validate_candidate_runtime_identity(identity, profile=profile)
        if not validation.valid:
            return CandidateRuntimeRegistrationResult(False, errors=validation.errors)

        record = build_candidate_registry_record(profile=profile, identity=identity, now_at=now_at)
        existing = self._registry_service.read_registry_record(identity.agent_id, now_at=now_at)
        if existing.accepted and existing.record is not None:
            conflict_errors = _active_runtime_conflict_errors(existing.record, identity)
            if conflict_errors:
                quarantine = self._registry_service.quarantine_agent(
                    identity.agent_id,
                    reason="DUPLICATE_ACTIVE_CANDIDATE_RUNTIME",
                    expected_revision=existing.revision,
                    now_at=now_at,
                )
                return CandidateRuntimeRegistrationResult(
                    accepted=False,
                    record=quarantine.record or existing.record,
                    revision=quarantine.revision or existing.revision,
                    errors=conflict_errors,
                    quarantined_existing=quarantine.accepted,
                )

        write = self._registry_service.register_or_refresh(
            record,
            expected_revision=expected_revision,
            now_at=now_at,
        )
        return _from_write_result(write)

    def evaluate_runtime_migration(self, request: CandidateRuntimeMigrationRequest) -> CandidateRuntimeMigrationDecision:
        errors: list[str] = []
        for field_name in (
            "agent_id",
            "candidate_profile_ref",
            "source_runtime_instance_id",
            "target_runtime_instance_id",
            "owner_principal_id",
            "runtime_provider",
            "migration_id",
            "evidence_ref",
        ):
            if not getattr(request, field_name):
                errors.append(f"MISSING_RUNTIME_MIGRATION_FIELD: {field_name}")
        if request.not_business_completion is not True:
            errors.append("RUNTIME_MIGRATION_CANNOT_BE_BUSINESS_COMPLETION")
        if request.source_runtime_instance_id == request.target_runtime_instance_id:
            errors.append("RUNTIME_MIGRATION_REQUIRES_DISTINCT_RUNTIME_IDS")
        return CandidateRuntimeMigrationDecision(accepted=not errors, errors=_dedupe(errors))


def _active_runtime_conflict_errors(
    existing: AgentRegistryRecord,
    identity: CandidateRuntimeIdentity,
) -> list[str]:
    if existing.registry_status != "active":
        return []
    same_profile = existing.candidate_profile_ref in (None, identity.candidate_profile_ref)
    if same_profile and existing.runtime_instance_id != identity.runtime_instance_id:
        return ["DUPLICATE_ACTIVE_CANDIDATE_RUNTIME"]
    if existing.candidate_profile_ref and existing.candidate_profile_ref != identity.candidate_profile_ref:
        return ["CANDIDATE_PROFILE_REF_CONFLICT"]
    return []


def _from_write_result(write: AgentRegistryWriteResult) -> CandidateRuntimeRegistrationResult:
    duplicate_suppressed = bool(write.event and write.event.event_type == "registry_record_unchanged")
    return CandidateRuntimeRegistrationResult(
        accepted=write.accepted,
        record=write.record,
        revision=write.revision,
        errors=write.errors,
        duplicate_suppressed=duplicate_suppressed,
    )


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
