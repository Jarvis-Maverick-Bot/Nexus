"""Health and readiness snapshots for the source-only MQ foundation daemon."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nexus.mq.foundation_daemon_config import config_hash, subject_allowed, validate_foundation_daemon_config


def build_foundation_daemon_status(
    *,
    config: dict[str, Any],
    broker_ready: bool = False,
    jetstream_ready: bool = False,
    consumer_ready: bool = False,
    evidence_ready: bool = True,
    state_store_ready: bool = True,
    inflight_count: int = 0,
    pending_retry_count: int = 0,
    dlq_count: int = 0,
    last_error: str | None = None,
) -> dict[str, Any]:
    validation = validate_foundation_daemon_config(config)
    flags = config.get("feature_flags", {}) if isinstance(config, dict) else {}
    daemon = config.get("daemon", {}) if isinstance(config, dict) else {}
    broker = config.get("broker", {}) if isinstance(config, dict) else {}
    allowlist = (config.get("subjects", {}) or {}).get("allowlist", []) if isinstance(config, dict) else []
    subject_allowlist_ready = (
        bool(allowlist)
        and subject_allowed(str(broker.get("filter_subject", "")), allowlist)
        and subject_allowed(str(broker.get("dlq_subject", "")), allowlist)
    )
    route_ready_source_only = (
        validation.valid
        and state_store_ready
        and evidence_ready
        and subject_allowlist_ready
        and daemon.get("default_enabled") is False
        and flags.get("business_dispatch_enabled") is False
        and flags.get("broker_setup_enabled") is False
    )
    live_publish_enabled = flags.get("live_publish_enabled") is True
    overall_ready = (
        route_ready_source_only
        and broker_ready
        and jetstream_ready
        and consumer_ready
        and live_publish_enabled
    )

    return {
        "schema_version": "3.5.foundation-daemon.status.v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "daemon_state": "source_only_default_off",
        "daemon_started": False,
        "overall_ready": overall_ready,
        "route_ready_source_only": route_ready_source_only,
        "config_ready": validation.valid,
        "config_hash": config_hash(config),
        "broker_ready": broker_ready,
        "jetstream_ready": jetstream_ready,
        "consumer_ready": consumer_ready,
        "evidence_ready": evidence_ready,
        "state_store_ready": state_store_ready,
        "subject_allowlist_ready": subject_allowlist_ready,
        "endpoint_contract_ready": True,
        "live_publish_enabled": live_publish_enabled,
        "business_dispatch_enabled": flags.get("business_dispatch_enabled") is True,
        "broker_setup_enabled": flags.get("broker_setup_enabled") is True,
        "inflight_count": inflight_count,
        "pending_retry_count": pending_retry_count,
        "dlq_count": dlq_count,
        "last_error": last_error,
        "last_transition_at": None,
        "evidence_refs": [],
        "not_live_uat": True,
        "not_business_completion": True,
    }
