"""Service boundary for persistent agent registry operations.

This service coordinates registry-store operations only. It does not start
runtime processes, perform dispatch, invoke private agents, or execute business
work.
"""

from __future__ import annotations

from typing import Optional

from nexus.mq.agent_registry import AgentRegistryRecord
from nexus.mq.agent_registry_store import (
    AgentRegistryLoadResult,
    AgentRegistryReadResult,
    AgentRegistryStore,
    AgentRegistryWriteResult,
)


class AgentRegistryService:
    def __init__(self, store: AgentRegistryStore):
        self._store = store

    def register_or_refresh(
        self,
        record: AgentRegistryRecord,
        *,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        return self._store.upsert_record(
            record,
            expected_revision=expected_revision,
            now_at=now_at,
        )

    def load_registry_records(self, *, now_at: Optional[str] = None) -> AgentRegistryLoadResult:
        return self._store.load_records(now_at=now_at)

    def read_registry_record(self, agent_id: str, *, now_at: Optional[str] = None) -> AgentRegistryReadResult:
        return self._store.get_record(agent_id, now_at=now_at)

    def quarantine_agent(
        self,
        agent_id: str,
        *,
        reason: str,
        expected_revision: Optional[int] = None,
        now_at: Optional[str] = None,
    ) -> AgentRegistryWriteResult:
        return self._store.quarantine_record(
            agent_id,
            reason=reason,
            expected_revision=expected_revision,
            now_at=now_at,
        )

    def write_presence_update(
        self,
        agent_id: str,
        *,
        runtime_instance_id: str,
        presence_state: str,
        heartbeat_at: str,
        heartbeat_sequence: Optional[int],
        expected_revision: int,
        load_score: float = 0.0,
        accepting_new_work: bool = True,
        evidence_refs: Optional[list[str]] = None,
        health_summary_ref: Optional[str] = None,
        event_type: str = "heartbeat_accepted",
        now_at: Optional[str] = None,
        allow_lifecycle_downgrade: bool = False,
    ) -> AgentRegistryWriteResult:
        return self._store.update_presence(
            agent_id,
            runtime_instance_id=runtime_instance_id,
            presence_state=presence_state,
            heartbeat_at=heartbeat_at,
            heartbeat_sequence=heartbeat_sequence,
            expected_revision=expected_revision,
            load_score=load_score,
            accepting_new_work=accepting_new_work,
            evidence_refs=evidence_refs,
            health_summary_ref=health_summary_ref,
            event_type=event_type,
            now_at=now_at,
            allow_lifecycle_downgrade=allow_lifecycle_downgrade,
        )

    def get_heartbeat_sequence(self, agent_id: str) -> Optional[int]:
        return self._store.get_heartbeat_sequence(agent_id)
