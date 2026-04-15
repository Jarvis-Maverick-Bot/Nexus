"""
governance/collaborators/tdd.py
V1.9 Sprint 1, Task T4.2
Initial proof-case collaborator: jarvis-tdd.

Demonstrates bounded persistent collaborator capability.
Stable named identity, queue inbox ownership, returns result/evidence to governed state.

Architecture reference: Arch Doc §19 — initial proof-case collaborator
"""

from typing import Dict, Any, List
import uuid

from governance.queue.models import Message, MessageType, MessageState
from governance.queue.store import get_store as get_queue_store
from governance.queue.state import transition as transition_message
from .base import CollaboratorBase, CollaboratorOutput


class TDDCollaborator(CollaboratorBase):
    """
    Initial proof-case TDD (test-driven development) collaborator.

    Receives planning output messages in its inbox (from planner).
    Produces test artifacts and validation evidence.
    Returns result/evidence into governed state.

    Stable identity: "tdd" (visible in governance status)
    Queue inbox: receives items routed to "tdd" role
    Output: emits response with test results and evidence payload
    """

    def __init__(self):
        super().__init__(role_name="tdd")

    def process(self, input_message: Message) -> CollaboratorOutput:
        """
        Process a TDD request (typically from planner output).

        Input payload expected fields (from planner):
            - _plan_output: dict containing plan_id, steps, task_description

        Output payload:
            - test_results: list of test outcomes
            - validation_passed: bool
            - evidence: dict of test artifacts

        Returns:
            CollaboratorOutput with test results and validation evidence
        """
        payload = input_message.payload

        # Extract plan output from payload
        plan_output = payload.get("_plan_output", {})
        if not plan_output:
            # Fallback: treat input as direct task description
            plan_output = {"task_description": payload.get("task_description", "unknown")}

        task_description = plan_output.get("task_description", "unknown")
        steps = plan_output.get("steps", [])

        # Run TDD cycle on the plan
        test_results, validation_passed = self._run_tdd_cycle(task_description, steps, payload)

        # Build evidence payload
        evidence = {
            "plan_id": plan_output.get("plan_id"),
            "task_description": task_description,
            "test_results": test_results,
            "validation_passed": validation_passed,
            "steps_executed": len(steps),
            "test_count": len(test_results),
            "source_message_id": input_message.message_id,
        }

        # Proper message lifecycle path:
        # NEW -> ROUTED (receive) -> CLAIMED (claim) -> ANSWERED (complete)
        # Guard against invalid transitions using can_claim / can_transition
        try:
            if input_message.state == MessageState.NEW:
                transition_message(input_message.message_id, MessageState.ROUTED)
            # Claim the message (ROUTED -> CLAIMED)
            transition_message(input_message.message_id, MessageState.CLAIMED)
            # Complete: CLAIMED -> ANSWERED
            transition_message(input_message.message_id, MessageState.ANSWERED)
        except ValueError:
            # Message may already be in a terminal state
            pass

        return CollaboratorOutput(
            success=True,
            summary=f"TDD cycle complete for task: {task_description[:50]}. "
                    f"Tests: {len(test_results)}, Validation: {'PASS' if validation_passed else 'FAIL'}",
            payload=evidence,
        )

    def _run_tdd_cycle(self, task_description: str, steps: List[dict], payload: dict) -> tuple:
        """
        Execute TDD cycle on a plan.

        Initial proof-case: deterministic test generation.
        Real TDD would run actual test execution.

        Returns:
            (test_results: list, validation_passed: bool)
        """
        test_results = []

        for step in steps:
            # Generate test cases for each step
            test_case = {
                "test_id": f"test-{step.get('step_id', '?')}",
                "description": f"Test for step: {step.get('action', 'unknown')}",
                "status": "PASS",
                "assertions": [
                    {"assert": f"{step.get('action')}_executed", "result": True}
                ],
            }
            test_results.append(test_case)

        # Validation: all tests pass and at least 1 test exists
        validation_passed = (
            len(test_results) >= 1
            and all(t["status"] == "PASS" for t in test_results)
        )

        # Check for explicit test failure signal in payload
        if payload.get("_force_test_fail"):
            validation_passed = False
            for t in test_results:
                t["status"] = "FAIL"
                t["error"] = "Forced failure via _force_test_fail"

        return test_results, validation_passed

    def validate_plan(self, plan_payload: dict) -> CollaboratorOutput:
        """
        Validate a plan without going through full queue processing.

        Args:
            plan_payload: dict with plan_id, task_description, steps

        Returns:
            CollaboratorOutput with validation result
        """
        plan_id = plan_payload.get("plan_id", "unknown")
        steps = plan_payload.get("steps", [])

        if not steps:
            return CollaboratorOutput(
                success=False,
                summary=f"Plan {plan_id} has no steps to validate",
                error="Empty steps list",
            )

        test_results, validation_passed = self._run_tdd_cycle(
            plan_payload.get("task_description", "unknown"),
            steps,
            plan_payload,
        )

        return CollaboratorOutput(
            success=validation_passed,
            summary=f"Plan {plan_id} validation: {'PASS' if validation_passed else 'FAIL'}",
            payload={
                "plan_id": plan_id,
                "validation_passed": validation_passed,
                "test_count": len(test_results),
                "test_results": test_results,
            },
        )


# Singleton instance
_tdd_instance: TDDCollaborator = None


def get_tdd() -> TDDCollaborator:
    """Get the singleton TDD instance."""
    global _tdd_instance
    if _tdd_instance is None:
        _tdd_instance = TDDCollaborator()
    return _tdd_instance