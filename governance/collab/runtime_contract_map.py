"""
Runtime Contract Map — Governance Contract Schema for Every Message Type
=======================================================================

Each message_type is a contract with explicit:
  - executor: who handles this step
  - mandatory_output: the business response that MUST be produced
  - completion_condition: what counts as "done" (NOT ACK)
  - notify_policy: who must be notified and when
  - auto_continue: whether handler should await/submit or return immediately

This is the source of truth for runtime behavior.
Loaded at startup; consulted by handlers on every message.

Three-layer architecture:
  Layer 1: Contract (governance boundary — 写死)
  Layer 2: Reasoning (AI model — bounded by contract, outputs DomainResult)
  Layer 3: Execution (runtime validates + converts DomainResult to CollabEnvelope)
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: Reasoning Output Objects
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DomainResult:
    """
    Reasoning layer 的标准输出对象。不是 transport envelope.
    Model 输出这个，Runtime 把它转成 CollabEnvelope。
    """
    message_type: str              # contract.mandatory_output
    collab_id: str
    from_: str
    result: str                   # enum: allowed_results 之一
    notes: str                    # 模型推理内容
    judgment_path: str = ""       # artifact 路径
    workflow: str = ""
    stage: str = ""
    extra: dict = field(default_factory=dict)  # 扩展字段


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Validation Objects
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReasoningValidation:
    """
    A层 — Reasoning output validation
    检查业务输出是否合法。
    """
    valid: bool
    result_enum_legal: bool        # result in allowed_results
    required_fields_present: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class EnvelopeValidation:
    """
    B层 — Transport/envelope validation
    检查协议边界是否合规。
    """
    valid: bool
    schema_compliant: bool          # CollabEnvelope 字段齐全
    protocol_compliant: bool       # from/to/collab_id/message_type 合法
    errors: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """
    两层校验合并结果。
    """
    reasoning: ReasoningValidation
    envelope: EnvelopeValidation

    def is_valid(self) -> bool:
        return self.reasoning.valid and self.envelope.valid


# ─────────────────────────────────────────────────────────────────────────────
# Contract Schema
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NotifyPolicy:
    channel: str           # 'telegram' | 'nats' | 'both'
    recipient: str        # 'alex' | 'nova' | 'jarvis'
    trigger: str          # 'on_start' | 'on_complete' | 'on_error' | 'on_exit'
    template: str         # message template


@dataclass
class StepContract:
    message_type: str
    description: str
    executor: str                   # 'nova' | 'jarvis'
    current_owner: str              # who owns the workflow at this step
    mandatory_output: str           # the business message_type that MUST be sent
    allowed_results: List[str]      # e.g. ['approved', 'revision_required', 'blocked']
    completion_condition: str        # what counts as step done (NOT ACK)
    notify_policy: List[NotifyPolicy] = field(default_factory=list)
    auto_continue: bool = True      # handler should submit next step automatically
    next_step: Optional[str] = None  # explicit next message_type in normal flow
    doctrine_loading_set: List[str] = field(default_factory=list)
    artifact_type: Optional[str] = None


# ── Contract Registry ───────────────────────────────────────────────────────────

CONTRACTS: dict[str, StepContract] = {

    # ── Foundation Create ───────────────────────────────────────────────────────

    "start_foundation_create": StepContract(
        message_type="start_foundation_create",
        description="Alex kicks off V2.0 Foundation Create. Nova is primary owner.",
        executor="nova",
        current_owner="nova",
        mandatory_output="review_request",
        allowed_results=["review_request"],
        completion_condition="review_request emitted on gov.collab.command to jarvis",
        notify_policy=[],
        auto_continue=True,
        next_step="review_request",
        doctrine_loading_set=["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"],
    ),

    "review_request": StepContract(
        message_type="review_request",
        description="Nova hands over Foundation draft to Jarvis for review.",
        executor="jarvis",
        current_owner="jarvis",
        mandatory_output="review_response",
        allowed_results=["approved", "revision_required", "blocked"],
        completion_condition="review_response delivered on gov.collab.command to nova",
        notify_policy=[
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_complete",
                         template="*Foundation Review Complete*\nCollab: `{collab_id}`\nResult: *{review_result}*")
        ],
        auto_continue=True,
        next_step=None,
        doctrine_loading_set=["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"],
        artifact_type="foundation",
    ),

    "review_response": StepContract(
        message_type="review_response",
        description="Jarvis delivers review judgment. Nova acts based on result.",
        executor="nova",
        current_owner="nova",
        mandatory_output="complete",
        allowed_results=["approved", "revision_required", "blocked"],
        completion_condition="complete delivered OR revised draft re-submitted",
        notify_policy=[
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_approved",
                         template="*Foundation — APPROVED*\nCollab: `{collab_id}`"),
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_revision_required",
                         template="*Foundation — Revision Required*\nCollab: `{collab_id}`"),
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_blocked",
                         template="*Foundation — BLOCKED*\nCollab: `{collab_id}`\nReason: {reason}"),
        ],
        auto_continue=False,
        next_step=None,
    ),

    "complete": StepContract(
        message_type="complete",
        description="Nova signals workflow complete. Jarvis acknowledges.",
        executor="jarvis",
        current_owner="nova",
        mandatory_output=None,
        allowed_results=[],
        completion_condition="state marked completed",
        notify_policy=[
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_complete",
                         template="*Foundation Create — COMPLETE*\nCollab: `{collab_id}`")
        ],
        auto_continue=False,
        next_step=None,
    ),

    "exit": StepContract(
        message_type="exit",
        description="Workflow aborted. Mandatory Telegram notification.",
        executor="jarvis",
        current_owner="nova",
        mandatory_output=None,
        allowed_results=[],
        completion_condition="state=exited + Telegram notified + processed ACK sent",
        notify_policy=[
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_exit",
                         template="*Foundation Create — EXITED*\nCollab: `{collab_id}`\nBy: {from_}\nReason: {reason}")
        ],
        auto_continue=False,
        next_step=None,
    ),

    # ── Operational messages ─────────────────────────────────────────────────

    "notify": StepContract(
        message_type="notify",
        description="Operational signal between agents.",
        executor="either",
        current_owner="",
        mandatory_output=None,
        allowed_results=[],
        completion_condition="message logged",
        notify_policy=[],
        auto_continue=False,
        next_step=None,
    ),

    "ping": StepContract(
        message_type="ping",
        description="Liveness check.",
        executor="jarvis",
        current_owner="",
        mandatory_output="pong",
        allowed_results=["pong"],
        completion_condition="pong received",
        notify_policy=[],
        auto_continue=False,
        next_step=None,
    ),

}


# ── Contract Lookup ───────────────────────────────────────────────────────────

def get_contract(message_type: str) -> Optional[StepContract]:
    """Look up the contract for a message type. Returns None if not found."""
    return CONTRACTS.get(message_type)


def is_terminal(message_type: str) -> bool:
    """True if this message type has no mandatory next output."""
    contract = get_contract(message_type)
    return contract is not None and contract.mandatory_output is None


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Runtime Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def runtime_validate(message_type: str, domain_result: DomainResult) -> ReasoningValidation:
    """
    A层 — Reasoning output validation
    校验模型输出是否符合 contract boundary。

    检查项：
    1. result 是否在 allowed_results
    2. required fields 是否齐全（collab_id, from_, message_type, result）
    """
    contract = get_contract(message_type)
    errors = []

    if contract is None:
        return ReasoningValidation(
            valid=False,
            result_enum_legal=False,
            required_fields_present=False,
            errors=[f"unknown message_type: {message_type}"]
        )

    # Rule 1: result must be in allowed_results
    if domain_result.result not in contract.allowed_results:
        errors.append(
            f"result '{domain_result.result}' not in allowed_results for {message_type} "
            f"(allowed: {contract.allowed_results})"
        )

    # Rule 2: required fields must be present
    for field_name in ['collab_id', 'from_', 'message_type', 'result']:
        if not getattr(domain_result, field_name, None):
            errors.append(f"required field '{field_name}' is missing")

    return ReasoningValidation(
        valid=len(errors) == 0,
        result_enum_legal=domain_result.result in contract.allowed_results,
        required_fields_present=len(errors) == 0,
        errors=errors
    )


def validate_envelope(envelope) -> EnvelopeValidation:
    """
    B层 — Transport/envelope validation
    校验 CollabEnvelope 是否符合协议边界。

    检查项：
    1. message_id / collab_id / from_ / to 是否齐全
    2. from_ 和 to 是否在 protocol 合法范围内（nova | jarvis）
    """
    errors = []

    if not getattr(envelope, 'message_id', None):
        errors.append("envelope.message_id is required")
    if not getattr(envelope, 'collab_id', None):
        errors.append("envelope.collab_id is required")
    if not getattr(envelope, 'from_', None):
        errors.append("envelope.from_ is required")
    if not getattr(envelope, 'to', None):
        errors.append("envelope.to is required")

    from_ = getattr(envelope, 'from_', None)
    to = getattr(envelope, 'to', None)

    if from_ and from_ not in ('nova', 'jarvis'):
        errors.append(f"envelope.from_ '{from_}' not in protocol (must be nova or jarvis)")
    if to and to not in ('nova', 'jarvis'):
        errors.append(f"envelope.to '{to}' not in protocol (must be nova or jarvis)")

    return EnvelopeValidation(
        valid=len(errors) == 0,
        schema_compliant=all([
            getattr(envelope, 'message_id', None),
            getattr(envelope, 'collab_id', None),
            getattr(envelope, 'from_', None),
            getattr(envelope, 'to', None),
        ]),
        protocol_compliant=(
            (from_ is None or from_ in ('nova', 'jarvis')) and
            (to is None or to in ('nova', 'jarvis'))
        ),
        errors=errors
    )


def validate_two_layer(message_type: str, domain_result: DomainResult, envelope) -> ValidationResult:
    """
    合并两层校验。
    先做 A层（reasoning），再做 B层（envelope）。
    """
    reasoning = runtime_validate(message_type, domain_result)
    envelope_check = validate_envelope(envelope)
    return ValidationResult(reasoning=reasoning, envelope=envelope_check)