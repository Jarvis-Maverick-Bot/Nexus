"""
governance/collaborators/planner.py
V1.9 Sprint 1, Task T4.1
Initial proof-case collaborator: jarvis-planner.

Demonstrates bounded persistent collaborator capability.
Stable named identity, queue inbox ownership, enqueue output to governed queue.

Architecture reference: Arch Doc §19 — initial proof-case collaborator
"""

from typing import Dict, Any
import uuid

from governance.queue.models import Message, MessageType
from .base import CollaboratorBase, CollaboratorOutput


class PlannerCollaborator(CollaboratorBase):
    """
    Initial proof-case planning collaborator.

    Receives planning request messages in its inbox.
    Produces structured planning output as a response message
    emitted back into the governed queue.

    Stable identity: "planner" (visible in governance status)
    Queue inbox: receives items routed to "planner" role
    Output: enqueues response to downstream collaborator (e.g., "tdd")
    """

    def __init__(self):
        super().__init__(role_name="planner")

    def process(self, input_message: Message) -> CollaboratorOutput:
        """
        Process a planning request.

        Input payload expected fields:
            - task_description: str — what to plan
            - constraints: dict — optional constraints
            - priority: str — optional priority hint

        Output payload:
            - plan_id: UUID of generated plan
            - steps: list of action items
            - estimated_outcome: str

        Returns:
            CollaboratorOutput with success/failure and plan payload
        """
        payload = input_message.payload

        # Validate required fields
        if "task_description" not in payload:
            return CollaboratorOutput(
                success=False,
                summary="Invalid planning request: missing task_description",
                error="task_description is required in payload",
            )

        task_description = payload["task_description"]
        constraints = payload.get("constraints", {})
        priority = payload.get("priority", "normal")

        # --- Planning logic (initial proof-case: simple structured output) ---
        # In V1.9 this is a demonstration of bounded persistent collaborator
        # behavior. Real planning capability would be more sophisticated.

        plan_id = f"plan-{input_message.message_id[:8]}"
        steps = self._generate_steps(task_description, constraints)

        output_payload = {
            "plan_id": plan_id,
            "task_description": task_description,
            "steps": steps,
            "priority": priority,
            "source_message_id": input_message.message_id,
        }

        # Emit planning output to tdd (downstream collaborator in direct queue delivery)
        output_msg = self.enqueue_output(
            receiver="tdd",
            payload={
                "_plan_output": output_payload,
                "_plan_type": "initial_proof_case",
            },
            original_message_id=input_message.message_id,
        )

        return CollaboratorOutput(
            success=True,
            summary=f"Plan {plan_id} generated for task: {task_description[:50]}",
            payload=output_payload,
            output_message_id=output_msg.message_id,
        )

    def _generate_steps(self, task_description: str, constraints: Dict[str, Any]) -> list:
        """
        Generate planning steps.

        Initial proof-case implementation: simple 3-step decomposition.
        Real implementation would use actual planning logic.
        """
        # Proof-of-concept step generation
        step_1 = {
            "step_id": "1",
            "action": "analyze",
            "description": f"Analyze requirements for: {task_description[:40]}",
            "depends_on": [],
        }
        step_2 = {
            "step_id": "2",
            "action": "design",
            "description": f"Design solution for: {task_description[:40]}",
            "depends_on": ["1"],
        }
        step_3 = {
            "step_id": "3",
            "action": "validate",
            "description": f"Validate plan for: {task_description[:40]}",
            "depends_on": ["2"],
        }

        steps = [step_1, step_2, step_3]

        # Apply constraint filtering (initial proof-case)
        if constraints.get("skip_validation"):
            steps = [s for s in steps if s["action"] != "validate"]

        return steps

    def emit_plan_preview(self, task_description: str) -> CollaboratorOutput:
        """
        Emit a preview plan without requiring a full message.

        Useful for direct invocation without queue round-trip.

        Returns:
            CollaboratorOutput with preview payload
        """
        plan_id = f"preview-{uuid.uuid4().hex[:8]}"
        steps = self._generate_steps(task_description, {})

        return CollaboratorOutput(
            success=True,
            summary=f"Preview plan {plan_id} generated",
            payload={
                "plan_id": plan_id,
                "task_description": task_description,
                "steps": steps,
                "type": "preview",
            },
        )


# Singleton instance
_planner_instance: PlannerCollaborator = None


def get_planner() -> PlannerCollaborator:
    """Get the singleton planner instance."""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = PlannerCollaborator()
    return _planner_instance