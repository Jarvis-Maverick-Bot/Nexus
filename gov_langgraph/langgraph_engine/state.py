"""
langgraph_engine.state — GovernanceState for LangGraph

One graph run = one workitem.
State carries only that workitem's data through the graph.

GovernanceState fields:
- project_id: str — project this workitem belongs to
- task_id: str — the workitem being processed
- workitem: WorkItem | None — the workitem object (loaded from StateStore)
- task_state: TaskState | None — current task state
- pending_handoffs: list[Handoff] — active handoffs
- gates: dict[str, Gate] — gate decisions (gate_id -> Gate)
- event_log: list[Event] — events emitted during this graph run
- current_action: str — command from last node: advance | block | handoff | halt | gate_approved | gate_rejected | done
- halt_reason: str | None — set when current_action = "halt"
- blocked: bool — whether task is currently blocked
- blocker: str | None — description of blocker if blocked
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from gov_langgraph.platform_model import WorkItem, TaskState, Handoff, Gate, Event


@dataclass
class GovernanceState:
    """
    LangGraph state for one workitem's journey through the pipeline.

    One graph run = one workitem.
    """

    # Identity
    project_id: str = ""
    task_id: str = ""

    # Core objects (loaded from StateStore by nodes)
    workitem: Optional[WorkItem] = None
    task_state: Optional[TaskState] = None

    # Active objects
    pending_handoffs: list[Handoff] = field(default_factory=list)
    gates: dict[str, Gate] = field(default_factory=dict)

    # Run log
    event_log: list[Event] = field(default_factory=list)

    # Graph command (set by nodes to direct routing)
    current_action: str = "advance"  # advance | block | handoff | halt | gate_approved | gate_rejected | done

    # Halt context
    halt_reason: Optional[str] = None

    # Blocker state
    blocked: bool = False
    blocker: Optional[str] = None

    def reset(self) -> None:
        """Reset runtime fields for a new graph run."""
        self.pending_handoffs = []
        self.gates = {}
        self.event_log = []
        self.current_action = "advance"
        self.halt_reason = None
        self.blocked = False
        self.blocker = None
