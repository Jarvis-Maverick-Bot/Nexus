"""Lifecycle plans for the source-only Layer 3 MQ foundation daemon package."""

from __future__ import annotations

from typing import Any


def build_restart_plan(config: dict[str, Any]) -> dict[str, Any]:
    daemon = config.get("daemon", {}) if isinstance(config, dict) else {}
    return {
        "service_name": daemon.get("service_name", "nexus-mq-foundation-daemon"),
        "actions": ["drain", "stop", "verify_offline", "start_after_later_authorization"],
        "source_package_default_off": True,
        "requires_later_runtime_authorization": True,
        "not_business_completion": True,
    }


def build_rollback_plan(config: dict[str, Any]) -> dict[str, Any]:
    daemon = config.get("daemon", {}) if isinstance(config, dict) else {}
    return {
        "service_name": daemon.get("service_name", "nexus-mq-foundation-daemon"),
        "actions": ["disable", "stop", "preserve_evidence", "preserve_durable_state"],
        "no_delete_no_overwrite": True,
        "requires_later_runtime_authorization": True,
        "not_business_completion": True,
    }


def build_drain_result(*, inflight_count: int = 0) -> dict[str, Any]:
    return {
        "drain_requested": True,
        "inflight_count": inflight_count,
        "offline_ready": inflight_count == 0,
        "daemon_started": False,
        "not_business_completion": True,
    }
