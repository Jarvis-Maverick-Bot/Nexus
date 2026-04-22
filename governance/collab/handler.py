"""
NATS Collaboration Mechanism - Message Handler
Event-driven skill dispatch from listener callback.
Phase 2: handlers are concrete, worker is recovery sweep only.

Three-layer architecture:
  Layer 1: Contract (governance boundary — 写死)
  Layer 2: Reasoning (AI model — bounded by contract, outputs DomainResult)
  Layer 3: Execution (runtime validates + converts DomainResult to CollabEnvelope)

This module implements the unified handler pipeline for all Foundation Create message types.
"""

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List
from .envelope import CollabEnvelope, AckEnvelope, VALID_MESSAGE_TYPES
from .state_store import CollabStateStore


# ── Subjects ───────────────────────────────────────────────────────────────────
_SUBJECTS = {
    'command': 'gov.collab.command',
    'ack': 'gov.collab.ack',
    'event': 'gov.collab.event',
    'notify': 'gov.collab.notify',
}


class _SubjectDict(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


SUBJECTS = _SubjectDict(_SUBJECTS)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Pipeline Infrastructure
# ─────────────────────────────────────────────────────────────────────────────

def _is_exited(collab_id: str, store: CollabStateStore) -> bool:
    """
    Runtime gate: check if collab is in exited state.
    All business messages for an exited collab must be rejected.
    """
    state = store.get_collab(collab_id)
    return state is not None and state.status == 'exited'


def _load_workflow_registry() -> dict:
    """Load workflow registry JSON for runtime routing/authorization hints."""
    from pathlib import Path
    import json

    registry_path = Path(__file__).parent / 'workflow_registry.json'
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _get_stage_binding(workflow: str, stage: str) -> dict:
    registry = _load_workflow_registry()
    return (
        registry.get('workflows', {})
        .get(workflow, {})
        .get('stages', {})
        .get(stage, {})
        .get('skill_handler_binding', {})
    ) or {}


def _get_next_receiver(domain, contract, store=None, fallback_from: str = None) -> str:
    """
    Determine who receives the next message.
    to 字段必须来自 contract routing context，禁止 from_ 反推。

    Priority:
    1. CollabState.receiver (stored routing context for this collab)
    2. contract.next_step's executor (if next_step is defined)
    3. fallback_from — the from_ of the inbound message (last hop sender)
    4. raise ValueError — no routing context available
    """
    from .runtime_contract_map import get_contract

    # Priority 1: routing context stored in collab state
    if store is not None:
        state = store.get_collab(domain.collab_id)
        if state is not None and getattr(state, 'receiver', None):
            return state.receiver

    # Priority 2: next_step's executor from contract
    if contract.next_step:
        next_contract = get_contract(contract.next_step)
        if next_contract:
            return next_contract.executor

    # Priority 3: fallback_from (inbound message's from_, i.e., who sent this message)
    if fallback_from in ('nova', 'jarvis'):
        return fallback_from

    # No routing context available — fail explicitly, no binary fallback
    raise ValueError(
        f"Cannot determine 'to' receiver for {contract.message_type}: "
        f"no CollabState.receiver and no next_step defined"
    )


def _domain_to_envelope(domain, contract, store=None) -> CollabEnvelope:
    """
    把 DomainResult 转成 transport CollabEnvelope。
    Model 不直接产生 envelope。Runtime 负责转换。

    to 字段来自 _get_next_receiver()，禁止 from_ 反推。
    store is passed to _get_next_receiver for CollabState.receiver lookup.
    """
    to_receiver = _get_next_receiver(domain, contract, store)

    payload = {
        'result': domain.result,
        'notes': domain.notes,
        'reasons': getattr(domain, 'reasons', '') or '',
        'required_changes': getattr(domain, 'required_changes', '') or '',
        'judgment_path': getattr(domain, 'judgment_path', ''),
        'workflow': getattr(domain, 'workflow', ''),
        'stage': getattr(domain, 'stage', ''),
        **getattr(domain, 'extra', {})
    }

    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None and v != ''}

    return CollabEnvelope(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        collab_id=domain.collab_id,
        message_type=contract.mandatory_output,
        from_=domain.from_,
        to=to_receiver,
        payload=payload,
        summary=f"{contract.message_type}: {domain.result}",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


def _build_envelope(
    message_type: str,
    collab_id: str,
    from_: str,
    to: str,
    summary: str,
    payload: dict,
    artifact_type: Optional[str] = None,
    artifact_path: Optional[str] = None
) -> CollabEnvelope:
    """Build a standard CollabEnvelope. Used for all outbound messages."""
    return CollabEnvelope(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        collab_id=collab_id,
        message_type=message_type,
        from_=from_,
        to=to,
        artifact_type=artifact_type,
        artifact_path=artifact_path,
        payload=payload,
        summary=summary,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


async def _apply_notify_policy(handler: 'CollabHandler', contract, domain, envelope: CollabEnvelope):
    """
    Send Telegram notifications per contract.notify_policy.
    Failures are logged but do not block pipeline.
    """
    for policy in contract.notify_policy:
        if policy.channel not in ('telegram', 'both'):
            continue
        try:
            from governance.collab.notify import send_telegram_notification_async

            template = policy.template
            # Replace placeholders
            template = template.replace('{collab_id}', envelope.collab_id)
            template = template.replace('{review_result}', getattr(domain, 'result', ''))
            template = template.replace('{from_}', envelope.from_)
            template = template.replace('{reason}', envelope.payload.get('reason', '') if envelope.payload else '')

            send_telegram_notification_async(template)
            handler._log("NOTIFY", f"[{envelope.collab_id}] Telegram sent to {policy.recipient}")
        except Exception as e:
            handler._log("WARN", f"[{envelope.collab_id}] Telegram notify failed: {e}")


async def _handle_failure(
    handler: 'CollabHandler',
    envelope: CollabEnvelope,
    contract,
    failure_type: str,
    errors: List[str],
    domain_result=None
):
    """
    Unified failure handler per failure matrix.

    Failure types:
    - doctrine_build_failed: doctrine context build 失败
    - reasoning_failed: reasoning step 失败
    - reasoning_validation_failed: reasoning output validation 失败
    - envelope_build_failed: envelope 构建 失败
    - nats_send_failed: NATS 发送失败（重试3次后）
    - persist_failed: state persist 失败

    State behavior per matrix:
    - doctrine_build_failed: pending_action 保持, last_event=failure_type
    - reasoning_failed: pending_action 保持, last_event=failure_type
    - reasoning_validation_failed: pending_action=awaiting_revision, last_event=failure_type
    - envelope_build_failed: status=failed, last_event=failure_type
    - nats_send_failed: status=failed, last_event=failure_type
    - persist_failed: status=failed, last_event=failure_type

    All failures write last_event。失败状态必须精确（包含 failure_type）。
    """
    handler._log("ERROR", f"[{envelope.collab_id}] {failure_type}: {errors}")

    # Determine state behavior per failure matrix
    failure_state_map = {
        'doctrine_build_failed': {'status': 'in_progress', 'pending_action': '', 'last_event': failure_type},
        'reasoning_failed':      {'status': 'in_progress', 'pending_action': '', 'last_event': failure_type},
        'reasoning_validation_failed': {'status': 'in_progress', 'pending_action': 'awaiting_revision', 'last_event': failure_type},
        'envelope_build_failed': {'status': 'failed', 'pending_action': '', 'last_event': failure_type},
        'nats_send_failed':      {'status': 'failed', 'pending_action': '', 'last_event': failure_type},
        'persist_failed':         {'status': 'failed', 'pending_action': '', 'last_event': failure_type},
    }

    state_update = failure_state_map.get(failure_type, {'status': 'failed', 'pending_action': '', 'last_event': failure_type})

    try:
        handler.store.update_collab(envelope.collab_id, **state_update)
    except Exception as e:
        handler._log("ERROR", f"[{envelope.collab_id}] persist_failed during failure handling: {e}")

    handler.store.emit_event(envelope.collab_id, failure_type, errors=errors)

    # Telegram notify for all failures (Alex must see)
    try:
        from governance.collab.notify import send_telegram_notification_async
        send_telegram_notification_async(
            f"*Pipeline Failure*\nCollab: `{envelope.collab_id}`\n"
            f"Type: {failure_type}\nErrors: {'; '.join(errors)}"
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Unified Handler Pipeline
# ─────────────────────────────────────────────────────────────────────────────

ReasoningFn = Callable[['CollabHandler', CollabEnvelope, Any], Any]
"""Async function: (handler, envelope, doctrine_context) -> DomainResult"""


async def run_pipeline(
    handler: 'CollabHandler',
    envelope: CollabEnvelope,
    contract,
    reasoning_fn: Optional[ReasoningFn] = None,
    doctrine_loading_set: Optional[List[str]] = None,
    workflow: str = 'v2_0',
    stage: str = '',
    skip_send: bool = False
) -> str:
    """
    Unified handler execution pipeline.

    Terminal step branch (mandatory_output=None or skip_send=True):
      Step 1: state=exited gate
      Step 2: doctrine context (if set)
      Step 3a: terminal — skip reasoning/validation/envelope/send
      Step 6: state update + notify

    Normal step branch (mandatory_output set and skip_send=False):
      Step 1: state=exited gate
      Step 2: doctrine context
      Step 3: reasoning_fn → DomainResult
      Step 4: A层校验 (reasoning output validation)
      Step 5: 构建 CollabEnvelope → B层校验
      Step 6: 发送消息 + 更新状态 + 通知

    Args:
        handler: CollabHandler instance
        envelope: inbound CollabEnvelope
        contract: StepContract for this message_type
        reasoning_fn: async fn(handler, envelope, doctrine_context) -> DomainResult
                      None for terminal steps
        doctrine_loading_set: list of doctrine names to load
        workflow: workflow identifier
        stage: stage identifier
        skip_send: if True, skip Steps 4-6 (for steps where current agent
                   does not produce an outbound business message)

    Returns:
        result string: 'completed' | failure_type
    """
    from .runtime_contract_map import runtime_validate, validate_envelope, DomainResult
    from .doctrine_bridge import build_doctrine_context

    # ── Step 0: state=exited gate ───────────────────────────────────
    if _is_exited(envelope.collab_id, handler.store):
        handler._log("WARN", f"[{envelope.collab_id}] rejecting message — collab is exited")
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    # ── Terminal step branch ─────────────────────────────────────────
    # mandatory_output=None (complete/exit) or skip_send=True (ack-only steps)
    is_terminal = (contract.mandatory_output is None) or skip_send

    # ── Step 2: Build doctrine context ───────────────────────────────
    doctrine_ctx = None
    if doctrine_loading_set and not is_terminal:
        try:
            doctrine_ctx = build_doctrine_context(doctrine_loading_set, workflow, stage)
        except Exception as e:
            await _handle_failure(handler, envelope, contract, 'doctrine_build_failed', [str(e)])
            return "doctrine_build_failed"

    if is_terminal:
        # Terminal path: no reasoning, no message sending
        # Only state update + notify
        handler.store.update_collab(
            envelope.collab_id,
            status='exited' if envelope.message_type == 'exit' else 'completed',
            pending_action='',
            last_event=f"{envelope.message_type}_completed"
        )
        handler.store.emit_event(envelope.collab_id, f"{envelope.message_type}_completed")

        # Apply notify policy if present
        if contract.notify_policy:
            domain = DomainResult(
                message_type=envelope.message_type,
                collab_id=envelope.collab_id,
                from_=handler.my_id,
                result='',
                notes='',
                workflow=workflow,
                stage=stage
            )
            dummy_envelope = CollabEnvelope(
                message_id=envelope.message_id,
                collab_id=envelope.collab_id,
                message_type=envelope.message_type,
                from_=handler.my_id,
                to='',
                payload={},
                summary=''
            )
            await _apply_notify_policy(handler, contract, domain, dummy_envelope)

        return "completed"

    # ── Normal step branch ───────────────────────────────────────────
    # ── Step 3: Call reasoning_fn ───────────────────────────────────
    domain_result = None
    if reasoning_fn is not None:
        try:
            domain_result = await reasoning_fn(handler, envelope, doctrine_ctx)
        except Exception as e:
            await _handle_failure(handler, envelope, contract, 'reasoning_failed', [str(e)])
            return "reasoning_failed"
    else:
        domain_result = DomainResult(
            message_type=contract.mandatory_output,
            collab_id=envelope.collab_id,
            from_=handler.my_id,
            result='',
            notes='',
            workflow=workflow,
            stage=stage
        )

    # ── Step 4: A层校验 ─────────────────────────────────────────────
    reasoning_check = runtime_validate(envelope.message_type, domain_result)
    if not reasoning_check.valid:
        await _handle_failure(
            handler, envelope, contract,
            'reasoning_validation_failed',
            reasoning_check.errors,
            domain_result
        )
        return "reasoning_validation_failed"

    # ── Step 5: 构建 envelope + B层校验 ─────────────────────────────
    try:
        outbound_envelope = _domain_to_envelope(domain_result, contract, handler.store)
    except Exception as e:
        await _handle_failure(handler, envelope, contract, 'envelope_build_failed', [str(e)])
        return "envelope_build_failed"

    envelope_check = validate_envelope(outbound_envelope)
    if not envelope_check.valid:
        await _handle_failure(
            handler, envelope, contract,
            'envelope_build_failed',
            envelope_check.errors
        )
        return "envelope_build_failed"

    # ── Step 6: 发送 + 状态 + 通知 ─────────────────────────────────
    sent = await _send_envelope(handler, outbound_envelope)
    if not sent:
        await _handle_failure(
            handler, envelope, contract,
            'nats_send_failed',
            [f"ACK not received after retries for {outbound_envelope.message_type}"]
        )
        return "nats_send_failed"

    handler.store.update_collab(
        envelope.collab_id,
        status='in_progress',
        pending_action='',
        last_event=f"{envelope.message_type}_completed"
    )

    await _apply_notify_policy(handler, contract, domain_result, outbound_envelope)

    return "completed"


# ─────────────────────────────────────────────────────────────────────────────
# Foundation Create Handlers (5 message types)
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_open(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'open' — create new collab, no further action."""
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    handler.store.update_collab(
        envelope.collab_id,
        status='open',
        current_owner=envelope.from_
    )
    return 'collab_opened'


async def _handle_start_foundation_create(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'start_foundation_create' — Jarvis-side kickoff handler only.

    Approved TC1 semantics:
      Nova -> start_foundation_create -> Jarvis
      Jarvis records kickoff state and sends workflow_started
      Nova continues only from workflow_started

    Nova must NOT execute drafting directly from this message type.
    """
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    workflow = ((envelope.payload or {}).get('workflow')) or 'v2_0'
    stage = ((envelope.payload or {}).get('stage')) or 'foundation_create'
    binding = _get_stage_binding(workflow, stage)
    authorized_receiver = binding.get('authorized_receiver', 'jarvis')

    if handler.my_id != authorized_receiver:
        handler._log(
            "WARN",
            f"[{envelope.collab_id}] start_foundation_create received by unauthorized agent "
            f"my_id={handler.my_id} authorized_receiver={authorized_receiver}, ignoring"
        )
        return "ignored"

    existing = handler.store.get_collab(envelope.collab_id)
    if existing is None:
        handler.store.open_collab(
            collab_id=envelope.collab_id,
            opened_by=envelope.from_,
            artifact_type=getattr(envelope, 'artifact_type', None) or 'foundation',
            artifact_path=getattr(envelope, 'artifact_path', None) or '',
            receiver='nova',
        )

    # Jarvis collaborator side: record kickoff state + send workflow_started
    handler.store.update_collab(
        collab_id=envelope.collab_id,
        status='open',
        current_owner='nova',
        receiver='nova',
        artifact_type='foundation',
        artifact_path=getattr(envelope, 'artifact_path', None) or '',
        pending_action='awaiting_foundation_draft',
        last_event='foundation_create_started',
        last_processed_by=handler.my_id
    )
    handler.store.emit_event(
        collab_id=envelope.collab_id,
        event='foundation_create_started',
        message_id=envelope.message_id,
        artifact_type='foundation',
        from_=envelope.from_
    )

    import uuid
    wf_started_envelope = CollabEnvelope(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        collab_id=envelope.collab_id,
        message_type="workflow_started",
        from_="jarvis",
        to="nova",
        payload={
            "workflow": "v2_0",
            "stage": "foundation_create",
            "message": "Foundation Create workflow started, Nova may begin drafting"
        },
        summary=f"workflow_started — Nova may begin drafting continuation"
    )
    handler.store.log_message(wf_started_envelope.as_dict(), 'OUT')
    await handler.nc.publish('gov.collab.command', wf_started_envelope.to_json())
    handler._log("HANDLER", f"[{envelope.collab_id}] workflow_started published (jarvis→nova)")
    return 'foundation_create_started'


async def _handle_workflow_started(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'workflow_started' — Nova receives Jarvis's business confirmation
    that the workflow has started. This is the TC1 continuation trigger.

    Nova side only (my_id == 'nova'):
      → update local collab state
      → execute_foundation_delivery (produce draft artifact)
      → send review_request to jarvis

    Jarvis side: should not receive workflow_started in normal flow
    (Jarvis sends it, Nova receives it).
    """
    from .foundation_executor import execute_foundation_delivery
    from .review_executor import _to_sharefolder_path

    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    workflow = ((envelope.payload or {}).get('workflow')) or 'v2_0'
    stage = ((envelope.payload or {}).get('stage')) or 'foundation_create'
    binding = _get_stage_binding(workflow, stage)
    continuation_receiver = envelope.to or 'nova'

    if handler.my_id != continuation_receiver:
        handler._log(
            "WARN",
            f"[{envelope.collab_id}] workflow_started received by unauthorized agent "
            f"my_id={handler.my_id} continuation_receiver={continuation_receiver}, ignoring"
        )
        return "ignored"

    # Authorized continuation receiver: trigger drafting
    # Update local state to reflect workflow is active and Nova owns drafting
    handler.store.update_collab(
        collab_id=envelope.collab_id,
        status='in_progress',
        current_owner='nova',
        receiver='jarvis',
        pending_action='drafting_in_progress',
        last_event='workflow_started_received',
        last_processed_by=handler.my_id
    )
    handler.store.emit_event(
        collab_id=envelope.collab_id,
        event='workflow_started_received',
        message_id=envelope.message_id,
        from_=envelope.from_,
        payload=envelope.payload or {}
    )
    handler._log("HANDLER", f"[{envelope.collab_id}] workflow_started received — Nova TC1 continuation triggered")

    # Execute Foundation delivery (produces draft artifact)
    task_context = {
        "collab_id": envelope.collab_id,
        "command_intent": "start_foundation_delivery",
        "doctrine_loading_set": ["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"],
        "artifact_binding": {"output_path": "governance/docs/V2_0_FOUNDATION.md"},
        "payload": envelope.payload or {}
    }
    await execute_foundation_delivery(handler, envelope.collab_id, task_context)

    # Get artifact_path from state (set by executor)
    state = handler.store.get_collab(envelope.collab_id)
    artifact_path = getattr(state, 'artifact_path', '') if state else ''

    # Convert local macOS path to sharefolder UNC path for Jarvis access
    artifact_path = _to_sharefolder_path(artifact_path)

    # Send review_request to Jarvis
    import uuid
    review_envelope = CollabEnvelope(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        collab_id=envelope.collab_id,
        message_type="review_request",
        from_="nova",
        to="jarvis",
        artifact_type='foundation',
        artifact_path=artifact_path,
        payload={
            "review_scope": "foundation completeness and governance alignment",
            "workflow": "v2_0",
            "stage": "foundation_create_review"
        },
        summary=f"Foundation draft ready for review — {envelope.collab_id}"
    )
    handler.store.log_message(review_envelope.as_dict(), 'OUT')
    await handler.nc.publish('gov.collab.command', review_envelope.to_json())
    handler._log("HANDLER", f"[{envelope.collab_id}] review_request published (nova→jarvis)")
    return 'workflow_started_triggered'


async def _handle_review_request(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'review_request' — Nova hands over draft to Jarvis for review.

    Contract-driven: mandatory_output = review_response.
    Pipeline: run_pipeline with execute_review as reasoning_fn.
    """
    from .runtime_contract_map import get_contract
    from .review_executor import execute_review, _to_sharefolder_path

    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    contract = get_contract('review_request')
    payload = envelope.payload or {}
    raw_artifact_path = payload.get('artifact_path', '')
    artifact_path = _to_sharefolder_path(raw_artifact_path)
    review_scope = payload.get('review_scope', 'foundation completeness and governance alignment')
    workflow = payload.get('workflow', 'v2_0')
    stage = payload.get('stage', 'foundation_create_review')

    # Update state: Jarvis owns the review stage
    handler.store.update_collab(
        envelope.collab_id,
        status='in_progress',
        current_owner='jarvis',
        receiver='nova',
        artifact_type=payload.get('artifact_type', 'foundation'),
        artifact_path=artifact_path,
        pending_action='awaiting_review_execution',
        last_event='review_handover_received',
        last_processed_by=handler.my_id
    )

    # Round control: enforce max_review_rounds
    state = handler.store.get_collab(envelope.collab_id)
    current_round = getattr(state, 'review_round', 0) or 0
    max_rounds = getattr(state, 'max_review_rounds', 3) or 3

    if current_round >= max_rounds:
        handler.store.update_collab(
            envelope.collab_id,
            status='blocked',
            pending_action='',
            termination_reason='max_review_rounds_exceeded',
            last_event='review_blocked_max_rounds'
        )
        handler.store.emit_event(
            envelope.collab_id,
            'review_blocked_max_rounds',
            review_round=current_round,
            max_review_rounds=max_rounds,
            termination_reason='max_review_rounds_exceeded'
        )
        handler._log("WARN", f"[{envelope.collab_id}] review_round={current_round} >= max={max_rounds} — BLOCKED")
        await handler._send_ack(envelope, 'processed', result='rejected_max_rounds_exceeded')
        return "max_review_rounds_exceeded"

    handler.store.update_collab(envelope.collab_id, review_round=current_round + 1)
    handler.store.emit_event(
        envelope.collab_id,
        'review_handover_received',
        message_id=envelope.message_id,
        skill='review_request',
        summary=envelope.summary,
        artifact_path=artifact_path,
        review_scope=review_scope,
        workflow=workflow,
        stage=stage
    )

    async def reasoning_fn(h, env, doctrine_ctx):
        result = await execute_review(
            h,
            collab_id=env.collab_id,
            artifact_path=artifact_path,
            review_scope=review_scope,
            doctrine_loading_set=contract.doctrine_loading_set
        )
        return result

    result = await run_pipeline(
        handler=handler,
        envelope=envelope,
        contract=contract,
        reasoning_fn=reasoning_fn,
        doctrine_loading_set=contract.doctrine_loading_set,
        workflow=workflow,
        stage=stage
    )

    if result == 'completed':
        handler.store.update_collab(
            envelope.collab_id,
            status='completed',
            pending_action='',
            last_event='review_completed'
        )

    return result


async def _handle_review_response(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'review_response' — Nova receives Jarvis's judgment.

    Behavior differs by agent:
    - Jarvis receives: record, no auto-follow-up (Jarvis is not the primary)
    - Nova receives: auto-decide next step based on review_result
    """
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    payload = envelope.payload or {}
    review_result = payload.get('result', 'unknown')
    review_notes = payload.get('notes', '')
    review_judgment_path = payload.get('judgment_path', '')

    handler.store.update_collab(
        envelope.collab_id,
        last_event='review_received',
        pending_action='',
        last_processed_by=handler.my_id
    )
    handler.store.emit_event(
        envelope.collab_id,
        'review_received',
        message_id=envelope.message_id,
        review_result=review_result,
        review_notes=review_notes
    )

    if handler.my_id == 'nova':
        if review_result == 'approved':
            complete_env = CollabEnvelope(
                message_id=f"msg-{uuid.uuid4().hex[:12]}",
                collab_id=envelope.collab_id,
                message_type='complete',
                from_='nova',
                to='jarvis',
                summary='Foundation Create workflow complete — approved by Jarvis review',
                payload={
                    'workflow': 'v2_0',
                    'stage': 'foundation_create_review',
                    'review_result': review_result,
                    'review_judgment_path': review_judgment_path
                }
            )
            await handler.nc.publish('gov.collab.command', complete_env.to_json())
            handler.store.log_message(complete_env.as_dict(), 'OUT')
            try:
                from governance.collab.notify import send_telegram_notification_async
                send_telegram_notification_async(
                    f"*Foundation Create — Complete*\n"
                    f"Collab: `{envelope.collab_id}`\n"
                    f"Result: *APPROVED*\n"
                    f"Review judgment: {review_judgment_path or 'N/A'}"
                )
            except Exception:
                pass
        elif review_result == 'revision_required':
            handler.store.update_collab(
                envelope.collab_id,
                status='in_progress',
                pending_action='awaiting_revision'
            )
            try:
                from governance.collab.notify import send_telegram_notification_async
                send_telegram_notification_async(
                    f"*Foundation Create — Revision Required*\n"
                    f"Collab: `{envelope.collab_id}`\n"
                    f"Notes: {review_notes[:200]}"
                )
            except Exception:
                pass
        elif review_result == 'blocked':
            try:
                from governance.collab.notify import send_telegram_notification_async
                send_telegram_notification_async(
                    f"*Foundation Create — BLOCKED*\n"
                    f"Collab: `{envelope.collab_id}`\n"
                    f"Reason: {review_notes[:200]}\n"
                    f"Human decision required"
                )
            except Exception:
                pass

    return 'review_received'


async def _handle_complete(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'complete' — mark collab completed.
    Terminal step: no reasoning needed.
    """
    from .runtime_contract_map import get_contract

    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    contract = get_contract('complete')

    handler.store.update_collab(
        envelope.collab_id,
        status='completed',
        pending_action='',
        last_event='collab_completed'
    )
    handler.store.emit_event(
        envelope.collab_id,
        'collab_completed',
        message_id=envelope.message_id
    )

    # Apply notify policy for complete
    from .runtime_contract_map import DomainResult
    domain = DomainResult(
        message_type='complete',
        collab_id=envelope.collab_id,
        from_=envelope.from_,
        result='',
        notes='',
        workflow='v2_0',
        stage='foundation_create'
    )
    await _apply_notify_policy(handler, contract, domain, envelope)

    return 'collab_completed'


async def _handle_exit(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'exit' — special termination path.

    Semantic (全部写死):
    1. Immediately interrupt ALL pending pipeline work
    2. State → 'exited', pending_action cleared
    3. Worker sweep must skip this collab (state=exited is a runtime gate)
    4. Send processed ACK (NOT business message)
    5. Telegram notify Alex (mandatory)
    6. Reject all subsequent business messages (state=exited is a runtime gate)

    This is NOT a normal handler template. Exit is special.
    """
    from .runtime_contract_map import get_contract

    handler._log("EXEC", f"[{envelope.collab_id}] exit triggered — interrupting pipeline")

    # Rule 2: State → exited
    handler.store.update_collab(
        envelope.collab_id,
        status='exited',
        pending_action='',
        last_event=f'collab_exited_by_{envelope.from_}'
    )

    # Rule 3: Emit event
    handler.store.emit_event(
        envelope.collab_id,
        'collab_exited',
        from_=envelope.from_,
        reason=envelope.payload.get('reason', '') if envelope.payload else ''
    )

    # Rule 4: Send processed ACK (not business message)
    await handler._send_ack(envelope, 'processed', result='')

    # Rule 5: Telegram notify (mandatory)
    try:
        from governance.collab.notify import send_telegram_notification_async
        send_telegram_notification_async(
            f"*Foundation Create — EXITED*\n"
            f"Collab: `{envelope.collab_id}`\n"
            f"By: {envelope.from_}\n"
            f"Reason: {envelope.payload.get('reason', 'No reason') if envelope.payload else 'No reason'}"
        )
    except Exception as e:
        handler._log("WARN", f"[{envelope.collab_id}] Telegram notification failed: {e}")

    return 'collab_exited'


async def _handle_decision_proposal(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'decision_proposal' — record proposal, set pending_action."""
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    handler.store.update_collab(
        envelope.collab_id,
        last_event='decision_proposed',
        pending_action='awaiting_decision'
    )
    handler.store.emit_event(
        envelope.collab_id,
        'decision_proposed',
        message_id=envelope.message_id
    )
    return 'decision_proposal_received'


async def _handle_decision_response(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'decision_response' — record decision, clear pending_action."""
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    handler.store.update_collab(
        envelope.collab_id,
        last_event='decision_received',
        pending_action=''
    )
    handler.store.emit_event(
        envelope.collab_id,
        'decision_received',
        message_id=envelope.message_id
    )
    return 'decision_received'


async def _handle_notify(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'notify' — log notification, no state change needed."""
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    handler.store.emit_event(
        envelope.collab_id,
        'notification_sent',
        message_id=envelope.message_id,
        payload=envelope.payload
    )
    return 'notification_sent'


async def _handle_ping(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'ping' — respond with pong."""
    return 'acknowledged'


async def _handle_unknown(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Fallback for unknown message types."""
    if _is_exited(envelope.collab_id, handler.store):
        await _send_ack(handler, envelope, 'received', result='rejected_collab_exited')
        return "rejected_exited"

    handler.store.emit_event(
        envelope.collab_id,
        'unknown_message_type',
        message_id=envelope.message_id,
        message_type=envelope.message_type
    )
    return 'unknown_message_type'


# Registry — maps message_type to skill handler
SKILL_REGISTRY: Dict[str, Callable] = {
    'open': _handle_open,
    'start_foundation_create': _handle_start_foundation_create,
    'workflow_started': _handle_workflow_started,
    'review_request': _handle_review_request,
    'review_response': _handle_review_response,
    'decision_proposal': _handle_decision_proposal,
    'decision_response': _handle_decision_response,
    'complete': _handle_complete,
    'exit': _handle_exit,
    'notify': _handle_notify,
    'ping': _handle_ping,
    'pong': _handle_ping,
}


class CollabHandler:
    """
    Main handler for inbound collaboration messages.

    Responsibilities:
    1. Validate incoming envelope
    2. Persist to durable store
    3. Emit received ACK
    4. Dispatch to skill handler (Phase 2: event-driven)
    5. Emit processed ACK
    """

    def __init__(self, nats_client, state_store: CollabStateStore, my_id: str):
        self.nc = nats_client
        self.store = state_store
        self.my_id = my_id  # 'jarvis' or 'nova'
        self._pending_ack: Dict[str, asyncio.Future] = {}

    def _log(self, level: str, line: str):
        """Log via daemon's log path."""
        from governance.collab.collab_daemon import _log_to_file, _paths
        try:
            p = _paths()
            _log_to_file(level, f"[{self.my_id}] {line}", p['daemon_log'])
        except Exception:
            print(f"[{level}] [{self.my_id}] {line}")

    async def handle_inbound(self, envelope: CollabEnvelope) -> bool:
        """
        Main entry point for inbound messages.
        Returns True if processed, False otherwise.
        """
        try:
            if not envelope.validate():
                self._log("WARN", f"Invalid envelope: {envelope.message_id}")
                return False

            # ── to 路由校验 ──────────────────────────────────────────────────────
            # 消息的 to 字段必须指向当前 daemon 的身份，否则拒绝处理
            # 这样可以防止双边 daemon 乱吃同一条消息
            if envelope.to and envelope.to != self.my_id:
                self._log("HANDLER", f"[REJECT] to={envelope.to} != my_id={self.my_id} — not for this daemon")
                return False

            # ── from 自检 ──────────────────────────────────────────────────────
            # 拒绝处理自己发出的消息（from == my_id）
            # 防止本地 daemon 把发出的消息当入站消息处理
            if envelope.from_ == self.my_id:
                self._log("HANDLER", f"[REJECT] from={envelope.from_} == my_id={self.my_id} — self-originated, ignoring")
                return False

            self.store.log_message(envelope.as_dict(), direction='IN')
            await self._send_ack(envelope, 'received')

            handler_fn = SKILL_REGISTRY.get(envelope.message_type, _handle_unknown)
            try:
                result = await handler_fn(self, envelope)
                self._log("HANDLER", f"[{envelope.collab_id}] {envelope.message_type} -> {result}")
            except Exception as e:
                self._log("ERROR", f"Handler error for {envelope.message_type}: {e}")
                result = f'error: {e}'

            await self._send_ack(envelope, 'processed', result=result)
            return True

        except Exception as e:
            self._log("ERROR", f"handle_inbound fatal: {e}")
            return False

    async def handle_ack(self, ack: AckEnvelope) -> bool:
        """
        Handle an ACK message — complete the pending Future.
        Returns True if this ACK was expected and matched, False otherwise.

        TC1 continuation trigger: when Nova receives ACK for start_foundation_create,
        trigger the foundation delivery + review_request handoff.
        """
        key = f"{ack.collab_id}:{ack.ack_for}"
        ack_matched = key in self._pending_ack
        if ack_matched:
            self._pending_ack[key].set_result(ack)
            del self._pending_ack[key]

        return ack_matched

    async def _send_ack(self, envelope: CollabEnvelope, ack_type: str, result: str = ''):
        """
        Emit an ACK for this envelope.

        ack_type: 'received' or 'processed'
        For 'received': use AckEnvelope.received()
        For 'processed': use AckEnvelope.processed()
        """
        if ack_type == 'received':
            ack = AckEnvelope.received(envelope, envelope.from_)
        else:
            ack = AckEnvelope.processed(envelope, envelope.from_, result)
        try:
            await self.nc.publish(SUBJECTS['ack'], ack.to_json())
            await self.nc.flush()
            # Log ACK OUT
            self.store.log_message(ack.as_dict(), 'OUT')
            self._log("ACK", f"[{envelope.collab_id}] sent {ack_type} ACK for {envelope.message_id} -> {envelope.from_}")
        except Exception as e:
            self._log("ERROR", f"Failed to send ACK: {e}")


async def _send_envelope(handler: 'CollabHandler', envelope: CollabEnvelope,
                          subject: str = 'gov.collab.command') -> bool:
    """
    Send a CollabEnvelope via NATS and wait for ACK.
    Returns True if ACK received within timeout, False otherwise.

    Retry policy: 3 attempts, 5s interval. After all retries fail → return False.
    """
    key = f"{envelope.collab_id}:{envelope.message_id}"
    loop = asyncio.get_event_loop()

    for attempt in range(3):
        future = loop.create_future()
        handler._pending_ack[key] = future

        try:
            await handler.nc.publish(subject, envelope.to_json())
            await handler.nc.flush()
            handler._log("SEND", f"[{envelope.collab_id}] {envelope.message_type} sent -> {envelope.to} (attempt {attempt + 1})")
            # Log OUT immediately after successful publish, before ACK wait
            handler.store.log_message(envelope.as_dict(), 'OUT')
        except Exception as e:
            handler._log("ERROR", f"[{envelope.collab_id}] send failed (attempt {attempt + 1}): {e}")
            handler._pending_ack.pop(key, None)
            if attempt == 2:
                return False
            await asyncio.sleep(5)
            continue

        try:
            await asyncio.wait_for(future, timeout=15.0)
            handler._log("ACK", f"[{envelope.collab_id}] ACK received for {envelope.message_type}")
            return True
        except asyncio.TimeoutError:
            handler._log("WARN", f"[{envelope.collab_id}] ACK timeout for {envelope.message_type} (attempt {attempt + 1})")
            handler._pending_ack.pop(key, None)
            if attempt == 2:
                return False
            await asyncio.sleep(5)
            continue

    return False
