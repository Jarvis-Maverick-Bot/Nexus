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

