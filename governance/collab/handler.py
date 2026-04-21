"""
NATS Collaboration Mechanism - Message Handler
Event-driven skill dispatch from listener callback.
Phase 2: handlers are concrete, worker is recovery sweep only.

Layer C binding for: "Start V2.0 Foundation Create" command.
Command intent: start_foundation_delivery
Workflow: v2_0 / stage: foundation_create
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from .envelope import CollabEnvelope, AckEnvelope, VALID_MESSAGE_TYPES
from .state_store import CollabStateStore


def _load_config() -> dict:
    config_path = Path(__file__).parent / "collab_config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


_config = _load_config()
_SUBJECTS = _config.get("subjects", {
    'command': 'gov.collab.command',
    'ack': 'gov.collab.ack',
    'event': 'gov.collab.event',
    'notify': 'gov.collab.notify'
})


class _SubjectDict(dict):
    """dict subclass so existing code using SUBJECTS['key'] keeps working."""
    pass


SUBJECTS = _SubjectDict(_SUBJECTS)


# ── Skill Handler Registry (Phase 2) ───────────────────────────────────
# Maps message_type → async handler function.
# Each handler: async def handler(handler: CollabHandler, envelope: CollabEnvelope) -> str
# Returns a result description string.

async def _handle_open(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'open' — create new collab, no further action."""
    handler.store.update_collab(
        envelope.collab_id,
        status='open',
        current_owner=envelope.from_
    )
    return 'collab_opened'


async def _handle_start_foundation_create(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'start_foundation_create' — initiates V2.0 Foundation delivery workflow.
    Layer C binding for: "Start V2.0 Foundation Create" command.
    Command intent: start_foundation_delivery

    Business logic:
    1. Create collab in 'open' state, owned by this agent (jarvis)
    2. Set pending_action to 'awaiting_foundation_draft'
    3. Emit foundation_create_started event
    4. Return result string for ACK

    This does NOT produce the artifact — skill/foundation_delivery handles that.
    This only opens the workflow and sets the governance state.

    Completion criteria:
    - collab.status = 'open'
    - collab.current_owner = handler.my_id
    - collab.pending_action = 'awaiting_foundation_draft'
    - collab.last_event = 'foundation_create_started'
    """
    handler.store.update_collab(
        envelope.collab_id,
        status='open',
        current_owner=handler.my_id,
        artifact_type='foundation',
        artifact_path='governance/docs/V2_0_FOUNDATION.md',
        pending_action='awaiting_foundation_draft',
        last_event='foundation_create_started'
    )
    handler.store.emit_event(
        envelope.collab_id,
        'foundation_create_started',
        message_id=envelope.message_id,
        command_intent=envelope.payload.get('command_intent', 'start_foundation_delivery'),
        workflow='v2_0',
        stage='foundation_create',
        artifact_type='foundation',
        artifact_path='governance/docs/V2_0_FOUNDATION.md'
    )
    return 'foundation_create_started'


async def _handle_foundation_draft_ready(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'foundation_draft_ready' — confirms foundation draft is ready for review.
    Triggered by the foundation_delivery skill after artifact is produced.

    Business logic:
    1. Update collab status to 'in_progress'
    2. Clear pending_action (draft is done)
    3. Set last_event to 'foundation_draft_ready'
    4. Emit event for audit trail

    Completion criteria:
    - collab.status = 'in_progress'
    - collab.pending_action = ''
    - collab.last_event = 'foundation_draft_ready'
    """
    handler.store.update_collab(
        envelope.collab_id,
        status='in_progress',
        pending_action='',
        last_event='foundation_draft_ready'
    )
    handler.store.emit_event(
        envelope.collab_id,
        'foundation_draft_ready',
        message_id=envelope.message_id,
        artifact_type='foundation',
        artifact_path='governance/docs/V2_0_FOUNDATION.md'
    )
    return 'foundation_draft_ready'


async def _handle_review_request(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """
    Handle 'review_request' — Nova hands over draft to Jarvis for review.
    
    Nova (primary executor) has produced a real Foundation draft.
    Jarvis (reviewer) receives it here and sets up review task.
    
    Payload expected:
      - command_intent: 'foundation_review_handover'
      - artifact_path: real path to Nova's draft
      - artifact_type: 'foundation'
      - review_scope: what Jarvis is judging
      - expected_output: 'review_response'
      - workflow: 'v2_0'
      - stage: 'foundation_create_review'
    """
    payload = envelope.payload or {}
    artifact_path = payload.get('artifact_path', '')
    review_scope = payload.get('review_scope', 'foundation completeness and governance alignment')
    expected_output = payload.get('expected_output', 'review_response')
    workflow = payload.get('workflow', 'v2_0')
    stage = payload.get('stage', 'foundation_create_review')

    # Store review context in collab state
    handler.store.update_collab(
        envelope.collab_id,
        status='in_progress',
        current_owner=handler.my_id,
        artifact_type=payload.get('artifact_type', 'foundation'),
        artifact_path=artifact_path,
        pending_action='awaiting_review_execution',
        last_event='review_handover_received'
    )
    handler.store.emit_event(
        envelope.collab_id,
        'review_handover_received',
        message_id=envelope.message_id,
        skill='review_request',
        summary=envelope.summary,
        artifact_path=artifact_path,
        review_scope=review_scope,
        expected_output=expected_output,
        workflow=workflow,
        stage=stage
    )
    return 'review_handover_received'


async def _handle_review_response(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'review_response' — record review result, close review."""
    handler.store.update_collab(
        envelope.collab_id,
        last_event='review_received',
        pending_action=''
    )
    handler.store.emit_event(
        envelope.collab_id,
        'review_received',
        message_id=envelope.message_id
    )
    return 'review_received'


async def _handle_decision_proposal(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'decision_proposal' — record proposal, set pending_action."""
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
    handler.store.update_collab(
        envelope.collab_id,
        last_event='decision_resolved',
        pending_action=''
    )
    handler.store.emit_event(
        envelope.collab_id,
        'decision_resolved',
        message_id=envelope.message_id
    )
    return 'decision_response_received'


async def _handle_complete(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'complete' — mark collab completed."""
    handler.store.update_collab(
        envelope.collab_id,
        status='completed',
        last_event='collab_completed',
        pending_action=''
    )
    handler.store.emit_event(
        envelope.collab_id,
        'collab_completed',
        message_id=envelope.message_id
    )
    return 'collab_completed'


async def _handle_exit(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'exit' — mark collab exited."""
    handler.store.update_collab(
        envelope.collab_id,
        status='exited',
        last_event='collab_exited',
        pending_action=''
    )
    handler.store.emit_event(
        envelope.collab_id,
        'collab_exited',
        message_id=envelope.message_id
    )
    return 'collab_exited'


async def _handle_notify(handler: 'CollabHandler', envelope: CollabEnvelope) -> str:
    """Handle 'notify' — log notification, no state change needed."""
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
    'foundation_draft_ready': _handle_foundation_draft_ready,
    'review_request': _handle_review_request,
    'review_response': _handle_review_response,
    'decision_proposal': _handle_decision_proposal,
    'decision_response': _handle_decision_response,
    'complete': _handle_complete,
    'exit': _handle_exit,
    'notify': _handle_notify,
    'ping': _handle_ping,
    'pong': _handle_ping,
    # 'ack' is handled via handle_ack, not here
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
        """Log via daemon's log path (uses store's log path)."""
        from governance.collab.collab_daemon import _log_to_file, _paths
        try:
            p = _paths()
            _log_to_file(level, f"[{self.my_id}] {line}", p['daemon_log'])
        except Exception:
            print(f"[{level}] [{self.my_id}] {line}")

    async def handle_inbound(self, envelope: CollabEnvelope) -> bool:
        """
        Process an inbound message — event-driven primary path.
        Returns True if processed successfully.
        Phase 2: skill dispatch happens here, no poll wait.
        """
        # 1. Validate
        if not self._validate(envelope):
            return False

        # 2. Selective receive: only process if addressed to this agent
        if envelope.to != self.my_id:
            return False

        # 3. Log inbound
        self.store.log_message(envelope.as_dict(), direction='inbound')

        # 4. Ensure collab exists in store
        self.store.get_or_create_collab(
            collab_id=envelope.collab_id,
            opened_by=envelope.from_,
            artifact_type=envelope.artifact_type,
            artifact_path=envelope.artifact_path
        )

        # 5. Update collab state to in_progress
        self.store.update_collab(
            envelope.collab_id,
            last_message_id=envelope.message_id,
            current_owner=self.my_id,
            status='in_progress'
        )

        # 6. Emit received ACK — we got the message
        await self._send_ack(envelope, 'received')

        # 7. SKILL DISPATCH — Phase 2: event-driven, no poll wait
        result = await self._skill_dispatch(envelope)

        # 8. Emit processed ACK — we're done processing
        await self._send_ack(envelope, 'processed', result)

        return True

    def _validate(self, envelope: CollabEnvelope) -> bool:
        """Validate envelope has required fields."""
        if not envelope.collab_id:
            return False
        if not envelope.message_type:
            return False
        if not envelope.from_:
            return False
        if envelope.message_type not in VALID_MESSAGE_TYPES:
            return False
        return True

    async def _skill_dispatch(self, envelope: CollabEnvelope) -> str:
        """
        Phase 2: Look up handler from registry and dispatch.
        Returns result string from the skill handler.
        """
        msg_type = envelope.message_type
        handler_fn = SKILL_REGISTRY.get(msg_type, _handle_unknown)
        return await handler_fn(self, envelope)

    async def _send_ack(self, for_envelope: CollabEnvelope, status: str, result: Optional[str] = None):
        """Send ACK for a message — received or processed."""
        ack = AckEnvelope(
            ack_for=for_envelope.message_id,
            collab_id=for_envelope.collab_id,
            from_=self.my_id,
            to=for_envelope.from_,
            status=status,
            result=result
        )
        payload = ack.to_json()
        await self.nc.publish(SUBJECTS['ack'], payload)
        await self.nc.flush()

        # Log outbound ACK
        self.store.log_message(ack.as_dict(), direction='outbound')

    async def handle_ack(self, ack: AckEnvelope):
        """Handle incoming ACK - complete the pending future."""
        if ack.ack_for in self._pending_ack:
            future = self._pending_ack[ack.ack_for]
            if not future.done():
                future.set_result(ack)

    async def send_command(self, collab_id: str, to: str, message_type: str,
                           summary: str = "", payload: Optional[dict] = None,
                           artifact_type: Optional[str] = None,
                           artifact_path: Optional[str] = None,
                           wait_for_ack: bool = True,
                           timeout: float = 10.0) -> tuple[bool, Optional[AckEnvelope]]:
        """
        Send a command message and optionally wait for ACK.
        Returns (sent, ack_result).
        """
        envelope = CollabEnvelope(
            collab_id=collab_id,
            message_type=message_type,
            from_=self.my_id,
            to=to,
            summary=summary,
            payload=payload or {},
            artifact_type=artifact_type,
            artifact_path=artifact_path
        )

        # Log outbound
        self.store.log_message(envelope.as_dict(), direction='outbound')

        # Update collab state
        self.store.get_or_create_collab(
            collab_id=collab_id,
            opened_by=self.my_id,
            artifact_type=artifact_type,
            artifact_path=artifact_path
        )
        self.store.update_collab(collab_id,
                                 last_message_id=envelope.message_id,
                                 current_owner=to)

        # Publish
        await self.nc.publish(SUBJECTS['command'], envelope.to_json())
        await self.nc.flush()

        if not wait_for_ack:
            return True, None

        # Wait for ACK
        try:
            ack = await self._wait_for_ack(envelope.message_id, timeout)
            return True, ack
        except asyncio.TimeoutError:
            return True, None

    async def _wait_for_ack(self, message_id: str, timeout: float) -> Optional[AckEnvelope]:
        """Wait for ACK for a specific message."""
        future: asyncio.Future = asyncio.Future()
        self._pending_ack[message_id] = future
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending_ack.pop(message_id, None)

    def get_collab_status(self, collab_id: str) -> Optional[dict]:
        """Get current status of a collaboration."""
        collab = self.store.get_collab(collab_id)
        if not collab:
            return None
        messages = self.store.get_messages(collab_id)
        return {
            "collab_id": collab_id,
            "status": collab.status,
            "current_owner": collab.current_owner,
            "last_message_id": collab.last_message_id,
            "last_event": collab.last_event,
            "pending_action": collab.pending_action,
            "message_count": len(messages)
        }