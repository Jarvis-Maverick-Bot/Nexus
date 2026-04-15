"""
governance/queue/linkage.py
V1.9 Sprint 1, Task T1.4
Message linkage and return association.

Establishes bidirectional links between request and response messages.
Return path chain is inspectable via governance inspect commands.

Key concepts:
- linked_response_id: this message -> response message
- Response messages carry their originating request's message_id
"""

from typing import List, Optional

from .models import Message, MessageState, MessageType
from .store import get_store


def link_request_to_response(request_id: str, response_id: str) -> Message:
    """
    Link a request message to its response message.

    Updates the request's linked_response_id to point at the response.
    """
    store = get_store()
    request = store.get(request_id)
    if request is None:
        raise KeyError(f"Request message {request_id} not found")
    request.link_response(response_id)
    store.update(request)
    return request


def link_response_to_request(response_id: str, request_id: str) -> Message:
    """
    Link a response message back to its originating request.

    Stores the request_id in the response's payload as metadata
    (since linked_response_id flows request -> response direction).
    """
    store = get_store()
    response = store.get(response_id)
    if response is None:
        raise KeyError(f"Response message {response_id} not found")
    # Ensure the response type is RESPONSE
    if response.type != MessageType.RESPONSE:
        raise ValueError(f"Message {response_id} is type {response.type.value}, not RESPONSE")
    # Store originating request in payload
    response.payload["_origin_request_id"] = request_id
    response.touch()
    store.update(response)
    return response


def get_response_for_request(request_id: str) -> Optional[Message]:
    """Get the response message linked to a given request."""
    store = get_store()
    request = store.get(request_id)
    if request is None:
        return None
    if request.linked_response_id is None:
        return None
    return store.get(request.linked_response_id)


def get_return_chain(message_id: str, max_depth: int = 10) -> List[dict]:
    """
    Build the return path chain for a message.

    Returns a list of dicts representing the chain from origin to latest response.
    Each entry: {message_id, type, state, is_origin}

    Args:
        message_id: starting message (typically a REQUEST)
        max_depth: maximum traversal depth to prevent cycles

    Returns:
        List of chain entries, origin first, response last
    """
    store = get_store()
    chain = []
    current_id = message_id
    visited = set()

    for _ in range(max_depth):
        if current_id in visited:
            break
        visited.add(current_id)

        msg = store.get(current_id)
        if msg is None:
            break

        chain.append({
            "message_id": msg.message_id,
            "type": msg.type.value,
            "state": msg.state.value,
            "sender": msg.sender,
            "receiver": msg.receiver,
            "is_origin": len(chain) == 0,
            "linked_response_id": msg.linked_response_id,
        })

        # Follow response link if present
        if msg.linked_response_id:
            current_id = msg.linked_response_id
        else:
            break

    return chain


def is_linked(message_id: str) -> bool:
    """Returns True if a message has a linked response."""
    store = get_store()
    msg = store.get(message_id)
    if msg is None:
        return False
    return msg.linked_response_id is not None


def get_origin_request(message_id: str) -> Optional[str]:
    """
    For a response message, retrieve the originating request message_id.

    Returns None if the message is not a response or has no origin recorded.
    """
    store = get_store()
    msg = store.get(message_id)
    if msg is None:
        return None
    return msg.payload.get("_origin_request_id")