"""
NATS Collaboration Mechanism - Core Envelope Schema
Protocol version: 0.2
"""

import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, Any
import json


@dataclass
class CollabEnvelope:
    """Standard message envelope for all NATS collaboration messages."""
    
    # Identity
    message_id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    collab_id: str = ""
    message_type: str = ""  # review_request, review_response, decision_proposal, ack, event, notify, complete, exit
    
    # Routing
    from_: str = ""  # 'jarvis' or 'nova'
    to: str = ""
    
    # Artifact reference (when applicable)
    artifact_type: Optional[str] = None  # foundation, scope, prd, etc.
    artifact_path: Optional[str] = None
    
    # Payload
    payload: dict = field(default_factory=dict)
    summary: str = ""
    
    # Protocol
    protocol_version: str = "0.2"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_json(self) -> bytes:
        return json.dumps(self.as_dict(), ensure_ascii=False).encode('utf-8')
    
    def as_dict(self) -> dict:
        d = asdict(self)
        d['from'] = d.pop('from_')
        return d
    
    @classmethod
    def from_json(cls, data: bytes) -> 'CollabEnvelope':
        d = json.loads(data.decode('utf-8'))
        d['from_'] = d.pop('from')
        return cls(**d)
    
    def is_ack_for(self, other: 'CollabEnvelope') -> bool:
        return self.payload.get('ack_for') == other.message_id


@dataclass
class AckEnvelope:
    """ACK response to a CollabEnvelope."""
    
    message_id: str = field(default_factory=lambda: f"ack-{uuid.uuid4().hex[:12]}")
    ack_for: str = ""  # message_id being acknowledged
    collab_id: str = ""
    
    # Routing
    from_: str = ""
    to: str = ""
    
    # ACK status
    status: str = ""  # 'received' or 'processed'
    result: Optional[str] = None  # e.g., 'review_started', 'artifact_updated', 'error'
    
    # Protocol
    protocol_version: str = "0.2"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def received(cls, for_msg: CollabEnvelope, to: str) -> 'AckEnvelope':
        return cls(
            ack_for=for_msg.message_id,
            collab_id=for_msg.collab_id,
            from_=for_msg.to,
            to=to,
            status='received'
        )
    
    @classmethod
    def processed(cls, for_msg: CollabEnvelope, to: str, result: str) -> 'AckEnvelope':
        return cls(
            ack_for=for_msg.message_id,
            collab_id=for_msg.collab_id,
            from_=for_msg.to,
            to=to,
            status='processed',
            result=result
        )
    
    def to_json(self) -> bytes:
        d = asdict(self)
        d['from'] = d.pop('from_')
        return json.dumps(d, ensure_ascii=False).encode('utf-8')
    
    @classmethod
    def from_json(cls, data: bytes) -> 'AckEnvelope':
        d = json.loads(data.decode('utf-8'))
        d['from_'] = d.pop('from')
        return cls(**d)


# Valid message types
VALID_MESSAGE_TYPES = {
    'review_request',
    'review_response', 
    'decision_proposal',
    'decision_response',
    'ack',
    'event',
    'notify',
    'complete',
    'exit',
    'open',
    'ping',
    'pong'
}

# Valid ACK statuses
VALID_ACK_STATUSES = {'received', 'processed'}

# Valid event types
VALID_EVENT_TYPES = {
    'collab_opened',
    'review_received',
    'review_started',
    'artifact_updated',
    'review_completed',
    'collab_closed',
    'blocker_raised',
    'decision_required'
}
