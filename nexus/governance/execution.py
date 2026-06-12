from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import ErrorCode
from .schemas import ActorRef, CommandEnvelope, ValidationResult, validate_command_envelope


EXECUTION_COMPONENT = "Project Execution"
EXECUTION_COMMAND_TYPES: tuple[str, ...] = (
    "CreateLayer1WorkPacket",
    "ValidatePacketMap",
    "MarkPacketReady",
    "CreatePacketRepairRequest",
    "SupersedeWorkPacket",
)
ALLOWED_EXECUTION_STATUSES: tuple[str, ...] = (
    "draft",
    "review",
    "ready",
    "submitted",
    "blocked",
    "revise",
    "revised",
    "deferred",
    "superseded",
    "active",
    "closed",
)
DOWNSTREAM_DISPATCH_STATUSES: tuple[str, ...] = (
    "dispatch",
    "accepted_for_dispatch",
    "dispatched",
    "returned_result_candidate",
    "returned_blocked",
    "accepted",
    "complete",
    "final_pass",
)
LAYER1_WORKPACKET_STATUSES: tuple[str, ...] = (
    "draft",
    "review",
    "ready",
    "blocked",
    "revise",
    "deferred",
    "superseded",
)
PACKET_READINESS_DECISION_STATUSES: tuple[str, ...] = (
    "ready",
    "blocked",
    "revise",
    "deferred",
    "superseded",
)
DISPATCH_BOUNDARY_PAYLOAD_KEYS: tuple[str, ...] = (
    "controller_ref",
    "controller_call",
    "controller_request",
    "controller_action",
    "dispatch_ref",
    "dispatch_contract_ref",
    "dispatch_contract_request",
    "dispatch_request",
    "dispatch_payload",
    "workpacket_dispatch_ref",
)
DISPATCH_BOUNDARY_STATUS_KEYS: tuple[str, ...] = (
    "status",
    "readiness_status",
    "requested_action",
    "action",
    "dispatch_status",
    "completion_status",
    "acceptance_status",
    "final_status",
)


@dataclass(frozen=True)
class ExecutionValidationResult:
    accepted: bool
    error_code: ErrorCode | None = None
    message: str = ""
    missing_fields: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    invalid_items: tuple[str, ...] = ()

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "blocked_reasons": list(self.blocked_reasons),
            "error_code": self.error_code.value if self.error_code else None,
            "invalid_items": list(self.invalid_items),
            "message": self.message,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class ApprovedExecutionPlanCandidateRef:
    project_id: str = ""
    plan_id: str = ""
    plan_version: int = 1
    kernel_acceptance_record_ref: str = ""
    approval_decision_ref: str = ""
    source_refs: tuple[str, ...] = ()
    planning_output_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectExecutionOutputBase:
    item_id: str = ""
    item_type: str = ""
    project_id: str = ""
    workspace_id: str = ""
    source_authority_refs: tuple[str, ...] = ()
    approved_plan_ref: str = ""
    workspace_manifest_ref: str = ""
    source_refs: tuple[str, ...] = ()
    status: str = ""
    owning_component: str = ""
    consumer_component_refs: tuple[str, ...] = ()
    version: int = 1
    supersedes: tuple[str, ...] = ()
    notes: str = ""
    created_by_component: str = EXECUTION_COMPONENT
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class PacketMap(ProjectExecutionOutputBase):
    packet_map_id: str = ""
    plan_ref: str = ""
    milestone_refs: tuple[str, ...] = ()
    packet_ids: tuple[str, ...] = ()
    dependency_graph_ref: str = ""
    excluded_work_refs: tuple[str, ...] = ()
    source_wbs_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PacketDependencyGraph(ProjectExecutionOutputBase):
    graph_id: str = ""
    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    prerequisites: dict[str, tuple[str, ...]] = field(default_factory=dict)
    blocked_edges: tuple[tuple[str, str], ...] = ()
    cycle_check_result: str = ""
    repair_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layer1WorkPacket(ProjectExecutionOutputBase):
    packet_id: str = ""
    packet_version: int = 1
    authority_refs: tuple[str, ...] = ()
    objective: str = ""
    work_type: str = ""
    scope: tuple[str, ...] = ()
    no_go: tuple[str, ...] = ()
    owner_role: str = ""
    reviewer_role: str = ""
    required_capability: str = ""
    expected_outputs: tuple[str, ...] = ()
    forbidden_outputs: tuple[str, ...] = ()
    validation_plan: tuple[str, ...] = ()
    evidence_contract_ref: str = ""
    acceptance_criteria: tuple[str, ...] = ()
    blocked_return_schema: dict[str, str] = field(default_factory=dict)
    stop_rules: tuple[str, ...] = ()
    human_review_required: bool = True
    controller_ref: str = ""
    dispatch_ref: str = ""


@dataclass(frozen=True)
class PacketReadinessDecision(ProjectExecutionOutputBase):
    decision_id: str = ""
    packet_ref: str = ""
    readiness_status: str = ""
    readiness_check_result: str = ""
    blocked_reason: str = ""
    reviewer_ref: str = ""
    kernel_record_ref: str = ""


@dataclass(frozen=True)
class PacketRepairRequest(ProjectExecutionOutputBase):
    request_id: str = ""
    packet_ref: str = ""
    failing_fields: tuple[str, ...] = ()
    reason: str = ""
    required_correction: str = ""
    owner: str = ""
    scope_change_ref: str = ""


@dataclass(frozen=True)
class PacketSupersedeRecord(ProjectExecutionOutputBase):
    supersede_id: str = ""
    old_packet_ref: str = ""
    new_packet_ref: str = ""
    reason: str = ""
    authority_ref: str = ""
    kernel_record_ref: str = ""


def validate_execution_output_base(item: ProjectExecutionOutputBase) -> ExecutionValidationResult:
    missing = _missing_fields(
        item,
        (
            "item_id",
            "item_type",
            "project_id",
            "workspace_id",
            "source_authority_refs",
            "approved_plan_ref",
            "workspace_manifest_ref",
            "source_refs",
            "status",
            "owning_component",
            "consumer_component_refs",
            "version",
        ),
    )
    blocked_reasons: list[str] = []
    if item.created_by_component != EXECUTION_COMPONENT:
        blocked_reasons.append("created_by_component must be Project Execution")
    if item.status and item.status not in ALLOWED_EXECUTION_STATUSES:
        blocked_reasons.append(f"invalid execution status: {item.status}")
    if not _is_positive_int(item.version):
        blocked_reasons.append("version must be a positive integer")
    if missing or blocked_reasons:
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_RECORD_INVALID,
            message="execution output base rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return ExecutionValidationResult(True, message="execution output base accepted")


def validate_approved_plan_ref(ref: ApprovedExecutionPlanCandidateRef) -> ExecutionValidationResult:
    missing = _missing_fields(ref, ("project_id", "plan_id", "plan_version", "source_refs", "planning_output_refs"))
    blocked_reasons: list[str] = []
    if not ref.approval_decision_ref:
        blocked_reasons.append("approved plan ref requires HumanDecision evidence")
    if not ref.kernel_acceptance_record_ref:
        blocked_reasons.append("approved plan ref requires Kernel baseline-entry evidence")
    if not _is_positive_int(ref.plan_version):
        blocked_reasons.append("plan_version must be a positive integer")
    if blocked_reasons:
        return ExecutionValidationResult(
            False,
            ErrorCode.MISSING_HUMAN_DECISION,
            message="approved execution plan ref rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return _record_result(missing, [])


def validate_packet_map(item: PacketMap) -> ExecutionValidationResult:
    base = validate_execution_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(
        item,
        (
            "packet_map_id",
            "plan_ref",
            "milestone_refs",
            "packet_ids",
            "dependency_graph_ref",
            "source_wbs_refs",
        ),
    )
    return _record_result(missing, [])


def validate_packet_dependency_graph(graph: PacketDependencyGraph) -> ExecutionValidationResult:
    base = validate_execution_output_base(graph)
    if not base.accepted:
        return base
    missing = _missing_fields(graph, ("graph_id", "nodes", "cycle_check_result"))
    nodes = set(graph.nodes)
    blocked_reasons: list[str] = []
    for start, end in graph.edges:
        if start not in nodes:
            blocked_reasons.append(f"missing dependency node: {start}")
        if end not in nodes:
            blocked_reasons.append(f"missing dependency node: {end}")
    for packet, prerequisites in graph.prerequisites.items():
        if packet not in nodes:
            blocked_reasons.append(f"missing dependency node: {packet}")
        for prerequisite in prerequisites:
            if prerequisite not in nodes:
                blocked_reasons.append(f"missing prerequisite node: {prerequisite}")
    if graph.blocked_edges and not graph.repair_refs:
        blocked_reasons.append("blocked dependency edges require repair refs")
    if _has_cycle(graph.nodes, graph.edges):
        blocked_reasons.append("dependency graph contains a cycle")
    return _record_result(missing, list(dict.fromkeys(blocked_reasons)))


def validate_layer1_workpacket(packet: Layer1WorkPacket) -> ExecutionValidationResult:
    base = validate_execution_output_base(packet)
    if not base.accepted:
        return base
    if packet.controller_ref or packet.dispatch_ref:
        blocked = []
        if packet.controller_ref:
            blocked.append("Layer1WorkPacket cannot include direct 4.19 controller refs")
        if packet.dispatch_ref:
            blocked.append("Layer1WorkPacket cannot include dispatch refs in Slice 004")
        return ExecutionValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="Layer1WorkPacket crossed Slice 004 boundary",
            blocked_reasons=tuple(blocked),
        )
    if packet.status not in LAYER1_WORKPACKET_STATUSES:
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_WORKPACKET_INVALID,
            message="Layer1WorkPacket status rejected",
            blocked_reasons=(f"Layer1WorkPacket status is not legal in Slice 004: {packet.status}",),
        )
    missing = _missing_fields(
        packet,
        (
            "packet_id",
            "packet_version",
            "authority_refs",
            "objective",
            "work_type",
            "scope",
            "no_go",
            "owner_role",
            "reviewer_role",
            "required_capability",
            "expected_outputs",
            "forbidden_outputs",
            "validation_plan",
            "evidence_contract_ref",
            "acceptance_criteria",
            "blocked_return_schema",
            "stop_rules",
        ),
    )
    if missing:
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_WORKPACKET_INVALID,
            message="Layer1WorkPacket contract incomplete",
            missing_fields=missing,
        )
    if not _is_positive_int(packet.packet_version):
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_WORKPACKET_INVALID,
            message="packet_version must be a positive integer",
            missing_fields=("packet_version",),
        )
    if packet.owner_role == packet.reviewer_role:
        return ExecutionValidationResult(
            False,
            ErrorCode.MISSING_HUMAN_DECISION,
            message="Layer1WorkPacket owner/reviewer conflict",
            blocked_reasons=("owner role cannot self-review packet readiness",),
        )
    return ExecutionValidationResult(True, message="Layer1WorkPacket contract accepted")


def validate_packet_readiness_decision(item: PacketReadinessDecision) -> ExecutionValidationResult:
    downstream_status = _first_downstream_status(item.status, item.readiness_status)
    if downstream_status:
        return ExecutionValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            message="packet readiness decision crossed Slice 004 boundary",
            blocked_reasons=(f"Slice 004 readiness cannot claim {downstream_status}",),
        )
    invalid_statuses = []
    if item.status not in PACKET_READINESS_DECISION_STATUSES:
        invalid_statuses.append(f"PacketReadinessDecision status is not legal in Slice 004: {item.status}")
    if item.readiness_status not in PACKET_READINESS_DECISION_STATUSES:
        invalid_statuses.append(
            f"PacketReadinessDecision readiness_status is not legal in Slice 004: {item.readiness_status}"
        )
    if invalid_statuses:
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_RECORD_INVALID,
            message="PacketReadinessDecision status rejected",
            blocked_reasons=tuple(invalid_statuses),
        )
    base = validate_execution_output_base(item)
    if not base.accepted:
        return base
    missing = _missing_fields(
        item,
        ("decision_id", "packet_ref", "readiness_status", "readiness_check_result", "reviewer_ref", "kernel_record_ref"),
    )
    return _record_result(missing, [])


def create_layer1_workpacket_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    project_id: str,
    workspace_id: str,
    approved_plan_ref: str,
    approval_decision_ref: str,
    kernel_acceptance_record_ref: str,
    workspace_manifest_ref: str,
    packet_id: str,
    packet_version: int,
    objective: str,
    work_type: str,
    scope: tuple[str, ...],
    no_go: tuple[str, ...],
    owner_role: str,
    reviewer_role: str,
    required_capability: str,
    expected_outputs: tuple[str, ...],
    forbidden_outputs: tuple[str, ...],
    validation_plan: tuple[str, ...],
    evidence_contract_ref: str,
    acceptance_criteria: tuple[str, ...],
    blocked_return_schema: dict[str, str],
    stop_rules: tuple[str, ...],
    human_review_required: bool,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreateLayer1WorkPacket",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "acceptance_criteria": acceptance_criteria,
            "approval_decision_ref": approval_decision_ref,
            "approved_plan_ref": approved_plan_ref,
            "blocked_return_schema": blocked_return_schema,
            "evidence_contract_ref": evidence_contract_ref,
            "expected_outputs": expected_outputs,
            "expected_version": expected_version,
            "forbidden_outputs": forbidden_outputs,
            "human_review_required": human_review_required,
            "idempotency_key": idempotency_key,
            "kernel_acceptance_record_ref": kernel_acceptance_record_ref,
            "no_go": no_go,
            "objective": objective,
            "owner_role": owner_role,
            "packet_id": packet_id,
            "packet_version": packet_version,
            "project_id": project_id,
            "projection_type": "execution-workpacket",
            "required_capability": required_capability,
            "reviewer_role": reviewer_role,
            "scope": scope,
            "source_refs": authority_refs,
            "stop_rules": stop_rules,
            "validation_plan": validation_plan,
            "work_type": work_type,
            "workspace_id": workspace_id,
            "workspace_manifest_ref": workspace_manifest_ref,
        },
    )


def validate_packet_map_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    project_id: str,
    workspace_id: str,
    approved_plan_ref: str,
    packet_map_ref: str,
    packet_ids: tuple[str, ...],
    dependency_graph_ref: str,
    expected_version: int,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="ValidatePacketMap",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=None,
        affects_state=False,
        payload={
            "approved_plan_ref": approved_plan_ref,
            "dependency_graph_ref": dependency_graph_ref,
            "expected_version": expected_version,
            "packet_ids": packet_ids,
            "packet_map_ref": packet_map_ref,
            "project_id": project_id,
            "projection_type": "execution-packet-map",
            "source_refs": authority_refs,
            "workspace_id": workspace_id,
        },
    )


def mark_packet_ready_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    packet_ref: str,
    packet_version: int,
    readiness_check_result_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="MarkPacketReady",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "packet_ref": packet_ref,
            "packet_version": packet_version,
            "projection_type": "execution-packet-readiness",
            "readiness_check_result_ref": readiness_check_result_ref,
            "source_refs": authority_refs,
        },
    )


def create_packet_repair_request_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    packet_ref: str,
    failing_fields: tuple[str, ...],
    reason: str,
    required_correction: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="CreatePacketRepairRequest",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "expected_version": expected_version,
            "failing_fields": failing_fields,
            "idempotency_key": idempotency_key,
            "packet_ref": packet_ref,
            "projection_type": "execution-packet-repair",
            "reason": reason,
            "required_correction": required_correction,
            "source_refs": authority_refs,
        },
    )


def supersede_workpacket_command(
    *,
    actor: ActorRef,
    authority_refs: tuple[str, ...],
    old_packet_ref: str,
    new_packet_payload: dict[str, Any],
    supersede_reason: str,
    authority_ref: str,
    expected_version: int,
    idempotency_key: str,
) -> CommandEnvelope:
    return CommandEnvelope(
        command_type="SupersedeWorkPacket",
        actor=actor,
        authority_refs=authority_refs,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        affects_state=False,
        payload={
            "authority_ref": authority_ref,
            "expected_version": expected_version,
            "idempotency_key": idempotency_key,
            "new_packet_payload": new_packet_payload,
            "old_packet_ref": old_packet_ref,
            "projection_type": "execution-packet-supersede",
            "source_refs": authority_refs,
            "supersede_reason": supersede_reason,
        },
    )


def validate_execution_command(command: CommandEnvelope) -> ValidationResult:
    validation = validate_command_envelope(command)
    if not validation.accepted:
        return validation
    if command.command_type not in EXECUTION_COMMAND_TYPES:
        return ValidationResult(False, ErrorCode.EXECUTION_COMMAND_INVALID, "unknown Project Execution command")
    for field_name in _required_payload_fields(command.command_type):
        if _payload_field_missing(command.payload, field_name):
            return ValidationResult(False, ErrorCode.EXECUTION_COMMAND_INVALID, f"{field_name} is required")
    source_refs = command.payload["source_refs"]
    if not isinstance(source_refs, (list, tuple)) or tuple(source_refs) != tuple(command.authority_refs):
        return ValidationResult(False, ErrorCode.EXECUTION_COMMAND_INVALID, "source_refs must match authority_refs")
    if not _is_non_negative_int(command.payload["expected_version"]):
        return ValidationResult(False, ErrorCode.EXECUTION_COMMAND_INVALID, "expected_version must be a non-negative integer")
    if not _payload_version_matches_envelope(command):
        return ValidationResult(
            False,
            ErrorCode.EXECUTION_COMMAND_INVALID,
            "payload expected_version must match envelope expected_version",
        )
    if "idempotency_key" in command.payload and command.payload["idempotency_key"] != command.idempotency_key:
        return ValidationResult(
            False,
            ErrorCode.EXECUTION_COMMAND_INVALID,
            "payload idempotency_key must match envelope idempotency_key",
        )
    if _command_crosses_dispatch_boundary(command):
        return ValidationResult(
            False,
            ErrorCode.NO_GO_BOUNDARY,
            "packet readiness command cannot dispatch or complete work",
        )
    command_specific = _validate_command_specific_contract(command)
    if not command_specific.accepted:
        return command_specific
    return ValidationResult(True)


def _required_payload_fields(command_type: str) -> tuple[str, ...]:
    if command_type == "CreateLayer1WorkPacket":
        return (
            "project_id",
            "workspace_id",
            "approved_plan_ref",
            "approval_decision_ref",
            "kernel_acceptance_record_ref",
            "workspace_manifest_ref",
            "packet_id",
            "packet_version",
            "objective",
            "work_type",
            "scope",
            "no_go",
            "source_refs",
            "owner_role",
            "reviewer_role",
            "required_capability",
            "expected_outputs",
            "forbidden_outputs",
            "validation_plan",
            "evidence_contract_ref",
            "acceptance_criteria",
            "blocked_return_schema",
            "stop_rules",
            "human_review_required",
            "expected_version",
            "idempotency_key",
        )
    if command_type == "ValidatePacketMap":
        return (
            "project_id",
            "workspace_id",
            "approved_plan_ref",
            "packet_map_ref",
            "packet_ids",
            "dependency_graph_ref",
            "source_refs",
            "expected_version",
        )
    if command_type == "MarkPacketReady":
        return ("packet_ref", "packet_version", "readiness_check_result_ref", "source_refs", "expected_version", "idempotency_key")
    if command_type == "CreatePacketRepairRequest":
        return ("packet_ref", "failing_fields", "reason", "required_correction", "source_refs", "expected_version", "idempotency_key")
    if command_type == "SupersedeWorkPacket":
        return (
            "old_packet_ref",
            "new_packet_payload",
            "supersede_reason",
            "authority_ref",
            "source_refs",
            "expected_version",
            "idempotency_key",
        )
    return ()


def _record_result(missing: tuple[str, ...], blocked_reasons: list[str]) -> ExecutionValidationResult:
    if missing or blocked_reasons:
        return ExecutionValidationResult(
            False,
            ErrorCode.EXECUTION_RECORD_INVALID,
            message="execution record rejected",
            missing_fields=missing,
            blocked_reasons=tuple(blocked_reasons),
        )
    return ExecutionValidationResult(True, message="execution record accepted")


def _missing_fields(item: object, field_names: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in field_names:
        if _payload_field_missing(item.__dict__, field_name):
            missing.append(field_name)
    return tuple(missing)


def _payload_field_missing(payload: dict[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        return True
    value = payload[field_name]
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (dict, list, set, tuple)):
        return len(value) == 0
    return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _payload_version_matches_envelope(command: CommandEnvelope) -> bool:
    return _is_non_negative_int(command.expected_version) and command.payload["expected_version"] == command.expected_version


def _first_downstream_status(*statuses: str) -> str:
    for status in statuses:
        if str(status).strip().lower() in DOWNSTREAM_DISPATCH_STATUSES:
            return str(status).strip().lower()
    return ""


def _command_crosses_dispatch_boundary(command: CommandEnvelope) -> bool:
    if _payload_crosses_dispatch_boundary(command.payload):
        return True
    new_packet_payload = command.payload.get("new_packet_payload")
    return isinstance(new_packet_payload, dict) and _payload_crosses_dispatch_boundary(new_packet_payload)


def _payload_crosses_dispatch_boundary(payload: dict[str, Any]) -> bool:
    for key in DISPATCH_BOUNDARY_PAYLOAD_KEYS:
        if _payload_field_missing(payload, key) is False:
            return True
    for status_field in DISPATCH_BOUNDARY_STATUS_KEYS:
        if _first_downstream_status(str(payload.get(status_field, ""))):
            return True
    if _nested_dispatch_intent(payload):
        return True
    return False


def _nested_dispatch_intent(payload: dict[str, Any]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if _payload_crosses_dispatch_boundary(value):
                return True
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict) and _payload_crosses_dispatch_boundary(item):
                    return True
    return False


def _validate_command_specific_contract(command: CommandEnvelope) -> ValidationResult:
    if command.command_type == "CreateLayer1WorkPacket":
        if not _is_positive_int(command.payload["packet_version"]):
            return ValidationResult(
                False,
                ErrorCode.EXECUTION_COMMAND_INVALID,
                "packet_version must be a positive integer",
            )
        if command.payload["owner_role"] == command.payload["reviewer_role"]:
            return ValidationResult(
                False,
                ErrorCode.MISSING_HUMAN_DECISION,
                "Layer1WorkPacket owner/reviewer conflict",
            )
    if command.command_type == "MarkPacketReady" and not _is_positive_int(command.payload["packet_version"]):
        return ValidationResult(
            False,
            ErrorCode.EXECUTION_COMMAND_INVALID,
            "packet_version must be a positive integer",
        )
    if command.command_type == "SupersedeWorkPacket":
        new_packet_payload = command.payload["new_packet_payload"]
        if (
            isinstance(new_packet_payload, dict)
            and "packet_version" in new_packet_payload
            and not _is_positive_int(new_packet_payload["packet_version"])
        ):
            return ValidationResult(
                False,
                ErrorCode.EXECUTION_COMMAND_INVALID,
                "new_packet_payload.packet_version must be a positive integer",
            )
    if (
        command.command_type == "CreatePacketRepairRequest"
        and command.payload.get("scope_change_ref")
        and not command.payload.get("human_decision_ref")
    ):
        return ValidationResult(
            False,
            ErrorCode.MISSING_HUMAN_DECISION,
            "scope-changing repair requires HumanDecision ref",
        )
    return ValidationResult(True)


def _has_cycle(nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...]) -> bool:
    graph: dict[str, list[str]] = {node: [] for node in nodes}
    for start, end in edges:
        graph.setdefault(start, []).append(end)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for next_node in graph.get(node, []):
            if visit(next_node):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in nodes)
