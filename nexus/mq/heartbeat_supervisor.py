"""Manual deterministic heartbeat supervisor for WBS 7.9.

This supervisor has no daemon loop and no live process start. Callers must
explicitly invoke `startup`, `run_cycle`, and `stop`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from nexus.mq.agent_registry_service import AgentRegistryService
from nexus.mq.heartbeat_policy import HeartbeatPolicy
from nexus.mq.heartbeat_presence_writer import HeartbeatPresenceWriter, HeartbeatWriteResult
from nexus.mq.heartbeat_runtime import HeartbeatPacket


SUPERVISOR_STATES = {"stopped", "starting", "active", "degraded", "stopping", "crashed"}


@dataclass
class HeartbeatSupervisorResult:
    accepted: bool
    supervisor_state: str
    errors: list[str] = field(default_factory=list)
    heartbeat_result: Optional[HeartbeatWriteResult] = None
    not_business_completion: bool = True


class HeartbeatSupervisor:
    def __init__(
        self,
        *,
        agent_id: str,
        runtime_instance_id: str,
        registry_service: AgentRegistryService,
        policy: Optional[HeartbeatPolicy] = None,
    ):
        self.agent_id = agent_id
        self.runtime_instance_id = runtime_instance_id
        self.policy = policy or HeartbeatPolicy()
        self._registry_service = registry_service
        self._writer = HeartbeatPresenceWriter(registry_service, self.policy)
        self.supervisor_state = "stopped"
        self._next_sequence = 1

    def startup(self, *, now_at: str) -> HeartbeatSupervisorResult:
        errors = self.policy.validate()
        self.supervisor_state = "starting"
        read = self._registry_service.read_registry_record(self.agent_id, now_at=now_at)
        if not read.accepted or read.record is None or read.revision is None:
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, [*errors, *read.errors])
        if read.record.runtime_instance_id != self.runtime_instance_id:
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, [*errors, "RUNTIME_INSTANCE_MISMATCH"])
        if read.record.registry_status != "active":
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, [*errors, f"REGISTRY_NOT_ACTIVE: {read.record.registry_status}"])
        if read.record.initialization_status != "ready":
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, [*errors, f"INITIALIZATION_NOT_READY: {read.record.initialization_status}"])
        if errors:
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, errors)
        previous_sequence = self._registry_service.get_heartbeat_sequence(self.agent_id)
        self._next_sequence = (previous_sequence or 0) + 1
        self.supervisor_state = "active"
        return HeartbeatSupervisorResult(True, self.supervisor_state)

    def run_cycle(
        self,
        *,
        now_at: str,
        desired_presence_state: str = "idle",
        load_score: float = 0.0,
        accepting_new_work: bool = True,
        evidence_refs: Optional[list[str]] = None,
        health_summary_ref: Optional[str] = None,
    ) -> HeartbeatSupervisorResult:
        if self.supervisor_state not in {"active", "degraded"}:
            return HeartbeatSupervisorResult(False, self.supervisor_state, ["SUPERVISOR_NOT_ACTIVE"])
        read = self._registry_service.read_registry_record(self.agent_id, now_at=now_at)
        if not read.accepted or read.record is None or read.revision is None:
            self.supervisor_state = "stopped"
            return HeartbeatSupervisorResult(False, self.supervisor_state, read.errors)
        if health_summary_ref and desired_presence_state == "idle":
            desired_presence_state = "degraded"
        packet = HeartbeatPacket(
            agent_id=self.agent_id,
            runtime_instance_id=self.runtime_instance_id,
            registry_revision_seen=read.revision,
            emitted_at=now_at,
            heartbeat_sequence=self._next_sequence,
            desired_presence_state=desired_presence_state,
            startup_packet_ref=read.record.startup_packet_ref or "",
            readiness_evidence_ref=read.record.readiness_evidence_ref or "",
            load_score=load_score,
            accepting_new_work=accepting_new_work,
            evidence_refs=list(evidence_refs or []),
            health_summary_ref=health_summary_ref,
        )
        heartbeat = self._writer.apply_heartbeat(packet, now_at=now_at)
        if heartbeat.accepted:
            self._next_sequence += 1
            if packet.desired_presence_state == "degraded":
                self.supervisor_state = "degraded"
            elif packet.desired_presence_state in {"draining", "offline"}:
                self.supervisor_state = "stopping"
            else:
                self.supervisor_state = "active"
        return HeartbeatSupervisorResult(
            heartbeat.accepted,
            self.supervisor_state,
            heartbeat.errors,
            heartbeat_result=heartbeat,
        )

    def stop(self, *, now_at: str) -> HeartbeatSupervisorResult:
        if self.supervisor_state == "stopped":
            return HeartbeatSupervisorResult(True, self.supervisor_state)
        result = self.run_cycle(
            now_at=now_at,
            desired_presence_state="offline",
            accepting_new_work=False,
            evidence_refs=["evidence://heartbeat/manual-stop"],
        )
        self.supervisor_state = "stopped" if result.accepted else "crashed"
        return HeartbeatSupervisorResult(result.accepted, self.supervisor_state, result.errors, result.heartbeat_result)
