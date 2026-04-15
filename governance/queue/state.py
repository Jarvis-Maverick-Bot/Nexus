"""
governance/queue/state.py
V1.9 Sprint 1, Task T1.3 (revised to match PRD V0_1 §5.A Req 1-5)
Queue state machine.

Exposes explicit transition rules and trigger documentation.
Coordinates with QueueStore to update message states.

Normal flow: NEW -> ROUTED -> CLAIMED -> WAITING -> ANSWERED -> CLOSED
Exception terminals: CANCELED, EXPIRED
"""

from typing import Dict, List, Optional, Tuple

from .models import Message, MessageState
from .store import get_store


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------
# Each entry: FROM_STATE -> (allowed TO_STATES, trigger_description)
_TRANSITIONS: Dict[MessageState, Tuple[List[MessageState], str]] = {
    MessageState.NEW: (
        [MessageState.ROUTED, MessageState.CANCELED, MessageState.EXPIRED],
        "NEW: messages start here. Route to target (ROUTED), cancel (CANCELED), or expire (EXPIRED)."
    ),
    MessageState.ROUTED: (
        [MessageState.CLAIMED, MessageState.CANCELED, MessageState.EXPIRED],
        "ROUTED: message has been routed to a receiver. Receiver claims it (CLAIMED), cancel (CANCELED), or expire (EXPIRED)."
    ),
    MessageState.CLAIMED: (
        [MessageState.WAITING, MessageState.ANSWERED, MessageState.CANCELED, MessageState.EXPIRED],
        "CLAIMED: receiver has claimed the message. "
        "Work in progress (WAITING), work complete (ANSWERED), cancel (CANCELED), or expire (EXPIRED)."
    ),
    MessageState.WAITING: (
        [MessageState.ANSWERED, MessageState.CANCELED, MessageState.EXPIRED],
        "WAITING: receiver is processing. Work complete (ANSWERED), cancel (CANCELED), or expire (EXPIRED)."
    ),
    MessageState.ANSWERED: (
        [MessageState.CLOSED],
        "ANSWERED: work is complete. Close the message (CLOSED)."
    ),
    MessageState.CLOSED: (
        [],
        "CLOSED: normal terminal state. No further transitions allowed."
    ),
    MessageState.CANCELED: (
        [],
        "CANCELED: cancelled by authorized action. Terminal state."
    ),
    MessageState.EXPIRED: (
        [],
        "EXPIRED: exceeded time-to-live. Terminal state."
    ),
}


def valid_next_states(from_state: MessageState) -> List[MessageState]:
    """Return list of valid next states from given state."""
    if from_state in _TRANSITIONS:
        return _TRANSITIONS[from_state][0]
    return []


def trigger_description(from_state: MessageState) -> str:
    """Return human-readable trigger description for a state."""
    if from_state in _TRANSITIONS:
        return _TRANSITIONS[from_state][1]
    return f"{from_state.value}: no transition rules defined."


def can_transition(from_state: MessageState, to_state: MessageState) -> bool:
    """Check if a transition is legally valid."""
    return to_state in valid_next_states(from_state)


def transition(message_id: str, to_state: MessageState) -> Message:
    """
    Transition a message to a new state.

    Args:
        message_id: the message to transition
        to_state: the target state

    Returns:
        The updated Message object

    Raises:
        KeyError: message not found
        ValueError: illegal transition attempt
    """
    store = get_store()
    message = store.get(message_id)
    if message is None:
        raise KeyError(f"Message {message_id} not found")

    if not can_transition(message.state, to_state):
        raise ValueError(
            f"Illegal transition attempted: {message.state.value} -> {to_state.value}. "
            f"Valid transitions from {message.state.value}: "
            f"{[s.value for s in valid_next_states(message.state)]}"
        )

    message.transition_to(to_state)
    store.update(message)
    return message


def get_state_info(state: MessageState) -> dict:
    """Return full state documentation for a given state."""
    return {
        "state": state.value,
        "valid_transitions": [s.value for s in valid_next_states(state)],
        "description": trigger_description(state),
        "is_terminal": state in (MessageState.CLOSED, MessageState.CANCELED, MessageState.EXPIRED),
    }


def all_states() -> List[MessageState]:
    """Return all defined message states in order."""
    return [
        MessageState.NEW,
        MessageState.ROUTED,
        MessageState.CLAIMED,
        MessageState.WAITING,
        MessageState.ANSWERED,
        MessageState.CLOSED,
        MessageState.CANCELED,
        MessageState.EXPIRED,
    ]