"""RunLedger transition guard for WBS 7.19."""

from __future__ import annotations

from dataclasses import dataclass, replace

from nexus.mq.structured_task_models import RunLedger


ALLOWED_TRANSITIONS = {
    "created": {"normalized"},
    "normalized": {"validated"},
    "validated": {"routed"},
    "routed": {"dispatched"},
    "dispatched": {"acked"},
    "acked": {"running"},
    "running": {"checkpointed", "interrupted", "timeout", "failed"},
    "checkpointed": {"running", "completed"},
    "interrupted": {"running"},
    "timeout": {"failed"},
    "failed": set(),
    "completed": set(),
}


@dataclass
class RunLedgerTransitionResult:
    ok: bool
    ledger: RunLedger
    errors: list[str]


def transition_runledger(
    ledger: RunLedger,
    to_state: str,
    *,
    evidence_ref: str,
) -> RunLedgerTransitionResult:
    errors: list[str] = []
    if not evidence_ref:
        errors.append("MISSING_TRANSITION_EVIDENCE")
    allowed = ALLOWED_TRANSITIONS.get(ledger.current_state, set())
    if to_state not in allowed:
        errors.append(f"INVALID_RUNLEDGER_TRANSITION: {ledger.current_state} -> {to_state}")
    if errors:
        return RunLedgerTransitionResult(False, ledger, errors)

    updated = replace(
        ledger,
        current_state=to_state,
        state_history=[*ledger.state_history, to_state],
        last_event_at=evidence_ref,
        completed_at=evidence_ref if to_state == "completed" else ledger.completed_at,
    )
    return RunLedgerTransitionResult(True, updated, [])
