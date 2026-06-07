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


def build_drain_result(
    *,
    inflight_count: int = 0,
    run_id: str | None = None,
    controlled_live: bool = False,
) -> dict[str, Any]:
    result = {
        "drain_requested": True,
        "inflight_count": inflight_count,
        "offline_ready": inflight_count == 0,
        "daemon_started": False,
        "not_business_completion": True,
    }
    if controlled_live:
        result.update(
            {
                "run_id": run_id,
                "controlled_live": True,
                "cleanup_evidenced": inflight_count == 0,
                "not_production_runtime": True,
            }
        )
    return result


def build_stop_result(
    *,
    run_id: str | None = None,
    controlled_live: bool = False,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    return {
        "timeout_seconds": timeout_seconds,
        "run_id": run_id,
        "controlled_live": controlled_live,
        "daemon_started": False,
        "offline": True,
        "cleanup_evidenced": True,
        "source_only_no_process_signal_sent": not controlled_live,
        "not_live_uat": not controlled_live,
        "not_production_runtime": True,
        "not_business_completion": True,
    }
