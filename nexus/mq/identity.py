"""
Skeleton identity/capability/authorization backend for protocol validation.

Phase 1 scope:
- load local YAML identity records
- validate §6.1 minimum required fields
- basic sender/target/capability authorization checks
"""

from dataclasses import dataclass, field
from typing import Optional
import yaml


AUTHORITY_VALID_MAPPING_STATES = {"resolved", "verified"}
NON_AUTHORITATIVE_MAPPING_STATES = {
    "unknown",
    "suspended",
    "revoked",
    "wrong_scope",
    "pending",
    "stale",
    "expired",
    "display_name_match",
    "display_name_similarity",
}


@dataclass
class IdentityValidationResult:
    valid: bool
    errors: list[str]
    resolved_principal_id: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class TrustMaterial:
    skeleton_shared_secret_ref: Optional[str] = None
    signature_key_ref: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass
class AgentIdentityRecord:
    agent_id: str
    display_name: str
    role: str
    machine_id: str
    environment: str
    runtime_instance_id: str
    status: str
    capabilities: list[str] = field(default_factory=list)
    authority_scopes: list[str] = field(default_factory=list)
    trusted_subject_prefixes: list[str] = field(default_factory=list)
    trust_material: TrustMaterial = field(default_factory=TrustMaterial)
    description: str = ""
    last_rotated_at: Optional[str] = None
    stages: list[str] = field(default_factory=list)

    def validate(self) -> IdentityValidationResult:
        errors: list[str] = []
        if not self.agent_id:
            errors.append("MISSING_REQUIRED_FIELD: agent_id")
        if not self.display_name:
            errors.append("MISSING_REQUIRED_FIELD: display_name")
        if not self.role:
            errors.append("MISSING_REQUIRED_FIELD: role")
        if not self.machine_id:
            errors.append("MISSING_REQUIRED_FIELD: machine_id")
        if not self.environment:
            errors.append("MISSING_REQUIRED_FIELD: environment")
        if not self.runtime_instance_id:
            errors.append("MISSING_REQUIRED_FIELD: runtime_instance_id")
        if self.status != "active":
            errors.append(f"INVALID_STATUS: {self.status}")
        if not self.capabilities:
            errors.append("MISSING_REQUIRED_FIELD: capabilities")
        if not self.authority_scopes:
            errors.append("MISSING_REQUIRED_FIELD: authority_scopes")
        if not self.trusted_subject_prefixes:
            errors.append("MISSING_REQUIRED_FIELD: trusted_subject_prefixes")
        if not self.trust_material.skeleton_shared_secret_ref and not self.trust_material.signature_key_ref:
            errors.append("MISSING_REQUIRED_FIELD: trust_material")
        return IdentityValidationResult(valid=len(errors) == 0, errors=errors)

    def authorizes(self, authority_scope: str) -> bool:
        return authority_scope in self.authority_scopes

    def supports_capability(self, capability: Optional[str]) -> bool:
        if capability is None:
            return True
        return capability in self.capabilities


class AgentIdentityStore:
    def __init__(self, agents: dict[str, AgentIdentityRecord]):
        self._agents = agents

    @classmethod
    def from_yaml_file(cls, path: str) -> "AgentIdentityStore":
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        agents: dict[str, AgentIdentityRecord] = {}
        for name, payload in (raw.get("agents") or {}).items():
            trust_material = TrustMaterial(**(payload.get("trust_material") or {}))
            record = AgentIdentityRecord(
                agent_id=payload.get("agent_id", ""),
                display_name=payload.get("display_name", name),
                role=payload.get("role", ""),
                machine_id=payload.get("machine_id", ""),
                environment=payload.get("environment", ""),
                runtime_instance_id=payload.get("runtime_instance_id", ""),
                status=payload.get("status", ""),
                capabilities=list(payload.get("capabilities") or []),
                authority_scopes=list(payload.get("authority_scopes") or []),
                trusted_subject_prefixes=list(payload.get("trusted_subject_prefixes") or []),
                trust_material=trust_material,
                description=payload.get("description", ""),
                last_rotated_at=payload.get("last_rotated_at"),
                stages=list(payload.get("stages") or []),
            )
            agents[record.agent_id] = record
        return cls(agents)

    def get_agent(self, agent_id: str) -> Optional[AgentIdentityRecord]:
        return self._agents.get(agent_id)

    def all_agents(self) -> list[AgentIdentityRecord]:
        return list(self._agents.values())

    def validate_store(self) -> IdentityValidationResult:
        errors: list[str] = []
        if not self._agents:
            errors.append("MISSING_REQUIRED_FIELD: agents")
        for agent_id, record in self._agents.items():
            result = record.validate()
            errors.extend([f"{agent_id}: {err}" for err in result.errors])
        return IdentityValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_sender(
        self,
        source_agent_id: str,
        source_role: str,
        authority_scope: str,
    ) -> IdentityValidationResult:
        record = self.get_agent(source_agent_id)
        if record is None:
            return IdentityValidationResult(valid=False, errors=[f"UNKNOWN_SENDER: {source_agent_id}"])
        errors: list[str] = []
        if record.role != source_role:
            errors.append(f"SOURCE_ROLE_MISMATCH: expected {record.role}, got {source_role}")
        if not record.authorizes(authority_scope):
            errors.append(f"UNAUTHORIZED_SCOPE: {authority_scope}")
        if record.status != "active":
            errors.append(f"INVALID_STATUS: {record.status}")
        return IdentityValidationResult(valid=len(errors) == 0, errors=errors)

    def validate_target_for_consumer(
        self,
        consumer_agent_id: str,
        target_agent_id: Optional[str] = None,
        target_role: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> IdentityValidationResult:
        consumer = self.get_agent(consumer_agent_id)
        if consumer is None:
            return IdentityValidationResult(valid=False, errors=[f"UNKNOWN_CONSUMER: {consumer_agent_id}"])

        errors: list[str] = []
        if target_agent_id and consumer.agent_id != target_agent_id:
            errors.append(f"INVALID_TARGET_AGENT: expected {target_agent_id}, got {consumer.agent_id}")
        if target_role and consumer.role != target_role:
            errors.append(f"TARGET_ROLE_MISMATCH: expected {target_role}, got {consumer.role}")
        if capability and not consumer.supports_capability(capability):
            errors.append(f"UNSUPPORTED_CAPABILITY: {capability}")
        return IdentityValidationResult(valid=len(errors) == 0, errors=errors)


@dataclass
class PrincipalIdentityMappingRecord:
    mapping_id: str
    channel_type: str
    actor_channel_identity_ref: str
    resolved_principal_id: Optional[str]
    permission_scope_ref: str
    mapping_state: str
    source_authority_ref: Optional[str]
    last_verified_at: Optional[str]
    evidence_refs: list[str] = field(default_factory=list)


def validate_principal_identity_mapping(
    record: PrincipalIdentityMappingRecord,
    *,
    required_permission_scope_ref: Optional[str] = None,
) -> IdentityValidationResult:
    errors: list[str] = []
    mapping_state = record.mapping_state.strip().lower() if record.mapping_state else ""
    if not mapping_state:
        errors.append("MISSING_MAPPING_STATE")
    elif mapping_state not in AUTHORITY_VALID_MAPPING_STATES and mapping_state not in NON_AUTHORITATIVE_MAPPING_STATES:
        errors.append(f"UNRECOGNIZED_MAPPING_STATE: {record.mapping_state}")
    elif mapping_state not in AUTHORITY_VALID_MAPPING_STATES:
        errors.append(f"NON_AUTHORITATIVE_MAPPING_STATE: {mapping_state}")
    if mapping_state == "unknown" or not record.resolved_principal_id:
        errors.append("UNKNOWN_IDENTITY")
    if mapping_state == "suspended":
        errors.append("SUSPENDED_PRINCIPAL")
    if mapping_state == "revoked":
        errors.append("REVOKED_PRINCIPAL")
    if mapping_state == "wrong_scope":
        errors.append("WRONG_SCOPE")
    if not record.source_authority_ref:
        errors.append("MISSING_SOURCE_AUTHORITY")
    if required_permission_scope_ref and record.permission_scope_ref != required_permission_scope_ref:
        errors.append("WRONG_SCOPE")
    return IdentityValidationResult(
        valid=not errors,
        errors=errors,
        resolved_principal_id=record.resolved_principal_id if not errors else None,
        evidence_refs=list(record.evidence_refs),
    )
