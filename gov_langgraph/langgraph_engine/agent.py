"""
langgraph_engine.agent — Role-Shaped Agent Definition

A role-shaped agent is a runtime-executing actor constrained by:
  1. Role identity
  2. Scope boundary
  3. Authority boundary
  4. Artifact obligation
  5. Runtime embodiment

Nova decision (2026-04-06): LOCKED for V1.
A role-shaped agent is NOT enough: SOUL.md alone or tools alone.
It must have all 5 properties.

Synchronous model: agent is invoked -> produces artifact -> returns -> pipeline decides.
No async, no background polling, no hidden control loops.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from gov_langgraph.platform_model import Role, V1_PIPELINE_STAGES
from gov_langgraph.platform_model.handoff_schema import HandoffDocument


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    HALTED = "halted"
    DENIED = "denied"


@dataclass
class RoleShapedAgent:
    """
    A runtime-executing actor constrained by role-specific
    identity, scope, authority, and artifact obligations.

    NOT just a spawned process or a bag of tools.
    Must have all 5 properties below.
    """

    # 1. Role identity
    role: Role
    role_name: str           # e.g. "viper_ba", "viper_sa"
    agent_id: str            # unique instance id

    # 2. Scope boundary — what stages this agent operates in
    allowed_stages: list[str] = field(default_factory=list)
    # e.g. viper_ba -> ["BA"], viper_sa -> ["SA"], viper_dev -> ["DEV"], viper_qa -> ["QA"]

    # 3. Authority boundary — what actions this agent can take
    allowed_actions: list[str] = field(default_factory=list)
    # e.g. ["create_artifact", "submit_handoff", "request_clarification"]

    # 4. Artifact obligation — what this agent must produce
    produces_artifact_type: str = ""
    # e.g. "BRD" for BA, "SPEC" for SA, "DELIVERABLE" for DEV, "QA_REPORT" for QA

    # 5. Runtime embodiment — current execution state
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    current_project_id: Optional[str] = None
    current_stage: Optional[str] = None
    halt_reason: Optional[str] = None

    def can_act_in_stage(self, stage: str) -> bool:
        """Check if this agent is allowed to operate in the given stage."""
        return stage in self.allowed_stages

    def can_take_action(self, action: str) -> bool:
        """Check if this agent is allowed to take the given action."""
        return action in self.allowed_actions

    def is_idle(self) -> bool:
        return self.status == AgentStatus.IDLE

    def is_running(self) -> bool:
        return self.status == AgentStatus.RUNNING

    def is_done(self) -> bool:
        return self.status == AgentStatus.DONE

    def is_halted(self) -> bool:
        return self.status == AgentStatus.HALTED

    def is_denied(self) -> bool:
        return self.status == AgentStatus.DENIED

    def execute(self, task_id: str, project_id: str, stage: str) -> HandoffDocument:
        """
        Execute one stage as this role-shaped agent.

        Synchronous: called by pipeline node, returns HandoffDocument.

        Raises:
            PermissionError — if agent is not allowed in this stage
            RuntimeError     — if agent is not in IDLE state
        """
        if not self.can_act_in_stage(stage):
            self.status = AgentStatus.DENIED
            raise PermissionError(
                f"Agent {self.role_name} denied: stage '{stage}' not in {self.allowed_stages}"
            )

        if not self.is_idle():
            raise RuntimeError(
                f"Agent {self.role_name} cannot execute: status is {self.status.value}, expected IDLE"
            )

        self.status = AgentStatus.RUNNING
        self.current_task_id = task_id
        self.current_project_id = project_id
        self.current_stage = stage

        # Build the handoff document
        # Note: artifact_references should be filled by caller with real artifacts.
        # Stub produces a placeholder reference.
        handoff = HandoffDocument(
            task_id=task_id,
            project_id=project_id,
            from_stage=stage,
            to_stage=_next_stage(stage),
            producer_role=self.role_name,
            artifact_references=[f"{self.produces_artifact_type.lower()}_artifacts"],
            handoff_summary=f"{self.role_name} completed stage {stage}",
            known_limitations="",
            next_expected_action=f"{_next_stage(stage)} to begin",
            status="pending_review",
        )

        self.status = AgentStatus.DONE
        return handoff

    def halt(self, reason: str):
        """Halt this agent mid-execution. Stores reason for audit."""
        self.status = AgentStatus.HALTED
        self.halt_reason = reason

    def to_dict(self) -> dict:
        return {
            "role_name": self.role_name,
            "agent_id": self.agent_id,
            "allowed_stages": self.allowed_stages,
            "allowed_actions": self.allowed_actions,
            "produces_artifact_type": self.produces_artifact_type,
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "current_project_id": self.current_project_id,
            "current_stage": self.current_stage,
        }


def _next_stage(current: str) -> str:
    """Get the next stage after current. Derived from V1_PIPELINE_STAGES."""
    try:
        idx = V1_PIPELINE_STAGES.index(current)
        return V1_PIPELINE_STAGES[idx + 1] if idx + 1 < len(V1_PIPELINE_STAGES) else "END"
    except ValueError:
        return "END"


# Pre-built role-shaped agents for V1
def make_viper_ba(agent_id: str = "viper_ba") -> RoleShapedAgent:
    return RoleShapedAgent(
        role=Role.VIPER_BA,
        role_name="viper_ba",
        agent_id=agent_id,
        allowed_stages=["BA"],
        allowed_actions=["create_artifact", "submit_handoff", "request_clarification", "flag_blocker"],
        produces_artifact_type="BRD",
    )


def make_viper_sa(agent_id: str = "viper_sa") -> RoleShapedAgent:
    return RoleShapedAgent(
        role=Role.VIPER_SA,
        role_name="viper_sa",
        agent_id=agent_id,
        allowed_stages=["SA"],
        allowed_actions=["create_artifact", "submit_handoff", "request_clarification", "flag_blocker"],
        produces_artifact_type="SPEC",
    )


def make_viper_dev(agent_id: str = "viper_dev") -> RoleShapedAgent:
    return RoleShapedAgent(
        role=Role.VIPER_DEV,
        role_name="viper_dev",
        agent_id=agent_id,
        allowed_stages=["DEV"],
        allowed_actions=["create_artifact", "submit_handoff", "request_clarification", "flag_blocker"],
        produces_artifact_type="DELIVERABLE",
    )


def make_viper_qa(agent_id: str = "viper_qa") -> RoleShapedAgent:
    return RoleShapedAgent(
        role=Role.VIPER_QA,
        role_name="viper_qa",
        agent_id=agent_id,
        allowed_stages=["QA"],
        allowed_actions=["create_artifact", "submit_handoff", "approve", "reject", "flag_blocker"],
        produces_artifact_type="QA_REPORT",
    )


def make_agent_for_stage(stage: str, agent_id: str = "") -> RoleShapedAgent:
    """Factory: get the right role-shaped agent for a given stage."""
    factories = {
        "BA": make_viper_ba,
        "SA": make_viper_sa,
        "DEV": make_viper_dev,
        "QA": make_viper_qa,
    }
    factory = factories.get(stage)
    if not factory:
        raise ValueError(f"No agent known for stage: {stage}")
    return factory(agent_id or f"viper_{stage.lower()}")
