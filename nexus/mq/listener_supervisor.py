"""Supervisor layer for Phase 3 always-on listener runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from nexus.mq.listener_runtime import ListenerRuntime, ListenerStartupResult, ListenerPollResult, TimeoutEmitResult


@dataclass
class SupervisorConfig:
    timeout_every_cycles: int = 5
    reconcile_every_cycles: int = 10
    stop_on_quarantine: bool = True


@dataclass
class SupervisorCycleResult:
    cycle_number: int
    poll_status: str
    timeout_published: int = 0
    reconciled_outbox_records: int = 0


@dataclass
class SupervisorRunSummary:
    startup: ListenerStartupResult
    cycles: list[SupervisorCycleResult]
    stopped_early: bool = False
    stop_reason: Optional[str] = None


class ListenerSupervisor:
    """Deterministic supervisor for orchestrating listener runtime cycles."""

    def __init__(
        self,
        listener: ListenerRuntime,
        config: Optional[SupervisorConfig] = None,
    ):
        self.listener = listener
        self.config = config or SupervisorConfig()
        self._cycle_count = 0
        self._startup: Optional[ListenerStartupResult] = None

    def startup(self) -> ListenerStartupResult:
        self._startup = self.listener.startup()
        return self._startup

    def run_cycle(self, now_at: Optional[str] = None) -> SupervisorCycleResult:
        self._cycle_count += 1
        poll = self.listener.poll_once()
        timeout_published = 0
        reconciled = 0

        if self._cycle_count % self.config.timeout_every_cycles == 0:
            timeout_result = self.listener.emit_timeouts_once(now_at=now_at)
            timeout_published = timeout_result.published_count

        if self._cycle_count % self.config.reconcile_every_cycles == 0:
            reconciled = self.listener.reconcile_outbox_once()

        return SupervisorCycleResult(
            cycle_number=self._cycle_count,
            poll_status=poll.status,
            timeout_published=timeout_published,
            reconciled_outbox_records=reconciled,
        )

    def run_cycles(self, total_cycles: int, now_at: Optional[str] = None) -> SupervisorRunSummary:
        startup = self._startup or self.startup()
        cycles: list[SupervisorCycleResult] = []

        if startup.quarantined and self.config.stop_on_quarantine:
            return SupervisorRunSummary(
                startup=startup,
                cycles=cycles,
                stopped_early=True,
                stop_reason="runtime_quarantined",
            )

        for _ in range(total_cycles):
            cycle = self.run_cycle(now_at=now_at)
            cycles.append(cycle)

        return SupervisorRunSummary(
            startup=startup,
            cycles=cycles,
        )

    def close(self) -> None:
        self.listener.close()
