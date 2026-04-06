"""
langgraph_engine.runtime — Runtime context for LangGraph Engine

Holds shared harness dependencies for the graph execution session.
Constructed once at session start, injected into nodes via context.

Usage:
    from gov_langgraph.langgraph_engine.runtime import init_runtime, get_runtime

    # At session/startup:
    init_runtime()

    # Inside nodes:
    rt = get_runtime()
    store = rt.store
    ckpt = rt.checkpointer
    journal = rt.event_journal
"""

from __future__ import annotations

from dataclasses import dataclass

from gov_langgraph.harness import HarnessConfig, StateStore, Checkpointer, EventJournal


@dataclass
class RuntimeContext:
    """
    Shared harness dependencies for a graph execution session.
    Initialized once at session start via init_runtime().
    """
    config: HarnessConfig
    store: StateStore
    checkpointer: Checkpointer
    event_journal: EventJournal


# Module-level singleton
_runtime: RuntimeContext | None = None


def init_runtime() -> RuntimeContext:
    """
    Initialize the runtime context. Call once per session.

    Returns:
        RuntimeContext with shared harness dependencies
    """
    global _runtime
    if _runtime is not None:
        return _runtime

    cfg = HarnessConfig()
    cfg.ensure_dirs()

    _runtime = RuntimeContext(
        config=cfg,
        store=StateStore(cfg.state_dir),
        checkpointer=Checkpointer(cfg),
        event_journal=EventJournal(cfg.event_dir),
    )
    return _runtime


def get_runtime() -> RuntimeContext:
    """
    Get the current runtime context.
    Raises RuntimeError if not initialized.
    """
    if _runtime is None:
        raise RuntimeError(
            "RuntimeContext not initialized. "
            "Call init_runtime() before running the graph."
        )
    return _runtime
