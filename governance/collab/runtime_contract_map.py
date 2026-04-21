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
"""

from dataclasses import dataclass, field
from typing import List, Optional


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
        mandatory_output="review_request",       # Nova must produce draft AND hand over
        allowed_results=["review_request"],       # only one valid output path
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
        mandatory_output="review_response",       # Jarvis MUST respond with judgment
        allowed_results=["approved", "revision_required", "blocked"],
        completion_condition="review_response delivered on gov.collab.command to nova",
        notify_policy=[
            NotifyPolicy(channel="telegram", recipient="alex",
                         trigger="on_complete",
                         template="*Foundation Review Complete*\nCollab: `{collab_id}`\nResult: *{review_result}*")
        ],
        auto_continue=True,
        next_step=None,                           # Nova decides based on result
        doctrine_loading_set=["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"],
        artifact_type="foundation",
    ),

    "review_response": StepContract(
        message_type="review_response",
        description="Jarvis delivers review judgment. Nova acts based on result.",
        executor="nova",
        current_owner="nova",
        mandatory_output="complete",               # Nova closes workflow after approval
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
        auto_continue=False,                      # Nova must decide next action
        next_step=None,
    ),

    "complete": StepContract(
        message_type="complete",
        description="Nova signals workflow complete. Jarvis acknowledges.",
        executor="jarvis",
        current_owner="nova",
        mandatory_output=None,                     # terminal step
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


def get_contract(message_type: str) -> Optional[StepContract]:
    """Look up the contract for a message type. Returns None if not found."""
    return CONTRACTS.get(message_type)


def is_terminal(message_type: str) -> bool:
    """True if this message type has no mandatory next output."""
    contract = get_contract(message_type)
    return contract is not None and contract.mandatory_output is None
