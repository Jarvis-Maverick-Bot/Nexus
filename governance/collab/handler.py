"""
NATS Collaboration Mechanism - Message Handler
Processes inbound commands, emits ACKs, updates state, fires events
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any
from .envelope import CollabEnvelope, AckEnvelope, VALID_MESSAGE_TYPES
from .state_store import CollabStateStore


SUBJECTS = {
    'command': 'gov.collab.command',
    'ack': 'gov.collab.ack',
    'event': 'gov.collab.event',
    'notify': 'gov.collab.notify'
}


class CollabHandler:
    """
    Main handler for inbound collaboration messages.

    Responsibilities:
    1. Validate incoming envelope
    2. Persist to durable store
    3. Emit ACK (received)
    4. Process the message
    5. Emit event
    6. Emit ACK (processed)
    """

    def __init__(self, nats_client, state_store: CollabStateStore, my_id: str):
        self.nc = nats_client
        self.store = state_store
        self.my_id = my_id  # 'jarvis' or 'nova'
        self._pending_ack: Dict[str, asyncio.Future] = {}

    async def handle_inbound(self, envelope: CollabEnvelope) -> bool:
        """
        Process an inbound message.
        Returns True if processed successfully.
        """
        # 1. Validate
        if not self._validate(envelope):
            return False

        # 2. Log inbound
        try:
            self.store.log_message(envelope.as_dict(), direction='inbound')
        except Exception as e:
            self._log_error(f"FATAL: log_message failed for {envelope.message_id}: {e}")
            # Cannot continue if durable logging fails — fail visible
            return False

        # 3. Ensure collab exists in store
        self.store.get_or_create_collab(
            collab_id=envelope.collab_id,
            opened_by=envelope.from_,
            artifact_type=envelope.artifact_type,
            artifact_path=envelope.artifact_path
        )

        # 4. Update collab state
        self.store.update_collab(
            envelope.collab_id,
            last_message_id=envelope.message_id,
            current_owner=self.my_id if envelope.to == self.my_id else envelope.to,
            status='in_progress'
        )

        # 5. Emit received ACK
        await self._send_ack(envelope, 'received')

        # 6. Process by message type
        result = await self._process(envelope)

        # 7. Emit event
        event_type = self._event_for_message(envelope, result)
        self.store.emit_event(envelope.collab_id, event_type,
                              message_id=envelope.message_id,
                              result=result)

        # 8. Emit processed ACK
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

    async def _send_ack(self, for_envelope: CollabEnvelope, status: str, result: Optional[str] = None):
        """Send ACK for a received message."""
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

        # Also log outbound ACK
        self.store.log_message(ack.as_dict(), direction='outbound')

    async def _process(self, envelope: CollabEnvelope) -> str:
        """Process message by type. Returns result string."""
        msg_type = envelope.message_type

        if msg_type == 'open':
            return 'collab_opened'

        elif msg_type == 'review_request':
            # Caller wants us to review something
            # State store already updated; caller handles actual review
            return 'review_started'

        elif msg_type == 'review_response':
            return 'review_received'

        elif msg_type == 'decision_proposal':
            return 'decision_proposal_received'

        elif msg_type == 'decision_response':
            return 'decision_response_received'

        elif msg_type == 'complete':
            self.store.update_collab(envelope.collab_id, status='completed')
            return 'collab_completed'

        elif msg_type == 'exit':
            self.store.update_collab(envelope.collab_id, status='exited')
            return 'collab_exited'

        elif msg_type in ('ping', 'pong', 'ack'):
            return 'acknowledged'

        elif msg_type == 'event':
            return envelope.payload.get('event', 'event_processed')

        elif msg_type == 'notify':
            return 'notification_sent'

        elif msg_type == 'diagnosis_request':
            # Business-layer diagnostic: update state but don't change collab status
            return 'diagnosis_request_received'

        elif msg_type == 'diagnosis_response':
            return 'diagnosis_response_received'

        elif msg_type == 'review_judgment':
            return 'review_judgment_received'

        elif msg_type == 'revision_request':
            return 'revision_request_received'

        elif msg_type == 'revision_update':
            return 'revision_update_received'

        elif msg_type == 'acceptance_proposal':
            return 'acceptance_proposal_received'

        elif msg_type == 'acceptance_confirmation':
            self.store.update_collab(envelope.collab_id, status='completed')
            return 'acceptance_confirmed'

        elif msg_type == 'blocker_notice':
            return 'blocker_noticed'

        else:
            return 'unknown_message_type'

    def _event_for_message(self, envelope: CollabEnvelope, result: str) -> str:
        """Map message type + result to canonical event name."""
        if envelope.message_type == 'open':
            return 'collab_opened'
        mapping = {
            ('review_request', 'review_started'): 'review_started',
            ('review_response', 'review_received'): 'review_received',
            ('decision_proposal', 'decision_proposal_received'): 'decision_proposed',
            ('complete', 'collab_completed'): 'collab_closed',
            ('exit', 'collab_exited'): 'collab_closed',
        }
        key = (envelope.message_type, result)
        return mapping.get(key, f'event_{result}')

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
            return True, ack  # sent=True, ack received
        except asyncio.TimeoutError:
            return True, None  # sent=True (published OK), but ACK timed out

    async def _wait_for_ack(self, message_id: str, timeout: float) -> Optional[AckEnvelope]:
        """Wait for ACK for a specific message."""
        future: asyncio.Future = asyncio.Future()
        self._pending_ack[message_id] = future
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending_ack.pop(message_id, None)

    async def handle_ack(self, ack: AckEnvelope):
        """Handle incoming ACK - complete the pending future."""
        if ack.ack_for in self._pending_ack:
            future = self._pending_ack[ack.ack_for]
            if not future.done():
                future.set_result(ack)

    def _log_error(self, msg: str):
        """Error logger for handler-level failures."""
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[{ts}][HANDLER_ERROR] {msg}")

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
