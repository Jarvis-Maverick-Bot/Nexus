"""
MQ Command Handler — 3.5 Implementation
Command message handler: picks up Command_Message, executes, produces result candidate.

Design source: GOVERNED_WORKFLOW_RUNTIME_AND_MESSAGE_QUEUE_ARCHITECTURE_V0_1.md §5.1
Baseline status: accepted-for-skeleton (3.5 V1.1, commit 3f7a5a0)

Handler responsibilities:
1. Validate envelope and correlation/workflow refs
2. Deduplicate by idempotency_key before side effects
3. Execute command and produce result candidate
4. Produce evidence refs and transition request
5. Pass to commit boundary for evidence/state commit
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any
import uuid


@dataclass
class HandlerResponse:
    """Response from command handler execution."""
    response_id: str = field(default_factory=lambda: f"hresp-{uuid.uuid4().hex[:12]}")
    workflow_instance_id: str = ""
    message_id: str = ""
    result_candidate: Optional[dict] = None
    evidence_refs: list[str] = field(default_factory=list)
    transition_request: Optional[dict] = None
    status: str = "candidate"   # candidate | committed | rejected
    error: Optional[str] = None


class CommandHandler:
    """
    Command message handler.

    Design rule: handler produces result CANDIDATE, not final result.
    Result becomes final only after commit boundary accepts evidence/state.
    """

    def __init__(self, idempotency_store, commit_boundary, ack_policy):
        self._idempotency_store = idempotency_store
        self._commit_boundary = commit_boundary
        self._ack_policy = ack_policy
        self._responses: list[HandlerResponse] = []

    def handle(
        self,
        envelope: dict,
        execute_command: Optional[callable] = None,
    ) -> HandlerResponse:
        """
        Handle a Command_Message envelope.

        Steps:
        1. Check idempotency before any side effects
        2. Execute command (if execute_command provided)
        3. Produce result candidate + evidence refs + transition request
        4. Submit to commit boundary
        5. Return handler response
        """
        message_id = envelope.get("message_id", "")
        workflow_instance_id = envelope.get("workflow_instance_id", "")
        idempotency_key = envelope.get("idempotency_key", "")
        payload = envelope.get("payload", {})

        # Step 1: idempotency check
        is_dup, record = self._idempotency_store.is_duplicate(
            idempotency_key, message_id, workflow_instance_id
        )
        if is_dup:
            response = HandlerResponse(
                workflow_instance_id=workflow_instance_id,
                message_id=message_id,
                status="rejected",
                error=f"IDEMPOTENCY_CONFLICT: duplicate message {message_id}",
            )
            self._responses.append(response)
            return response

        # Step 2: execute command if provided
        result_candidate = None
        if execute_command:
            try:
                result_candidate = execute_command(payload)
            except Exception as e:
                response = HandlerResponse(
                    workflow_instance_id=workflow_instance_id,
                    message_id=message_id,
                    status="rejected",
                    error=f"COMMAND_EXECUTION_FAILED: {e}",
                )
                self._responses.append(response)
                return response

        # Step 3: produce evidence refs and transition request
        evidence_refs = result_candidate.get("evidence_refs", []) if result_candidate else []
        transition_request = result_candidate.get("transition_request", {"new_state": "processing"}) if result_candidate else {"new_state": "processing"}

        commit_result = self._commit_boundary.try_commit(
            workflow_instance_id=workflow_instance_id,
            evidence_refs=evidence_refs,
            state_transition=transition_request,
        )

        status = "committed" if commit_result.accepted else "rejected"
        error = commit_result.error if not commit_result.accepted else None

        if commit_result.accepted:
            self._idempotency_store.record_processed(
                idempotency_key=idempotency_key,
                message_id=message_id,
                workflow_instance_id=workflow_instance_id,
                result="processed",
                result_detail=commit_result.commit_id,
            )

        response = HandlerResponse(
            workflow_instance_id=workflow_instance_id,
            message_id=message_id,
            result_candidate=result_candidate,
            evidence_refs=evidence_refs,
            transition_request=transition_request,
            status=status,
            error=error,
        )
        self._responses.append(response)
        return response

    def get_responses(self) -> list[HandlerResponse]:
        return list(self._responses)

    def clear(self):
        self._responses.clear()
