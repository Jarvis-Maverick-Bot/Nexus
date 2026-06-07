"""CLI for source-only Layer 3 MQ foundation daemon surfaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from nexus.mq.durable_state import DurableStateStore
from nexus.mq.foundation_daemon_config import (
    CONTROLLED_LIVE_RUN_SCOPE,
    is_controlled_live_requested,
    load_foundation_daemon_config,
    redact_config,
    validate_foundation_daemon_config,
)
from nexus.mq.foundation_daemon_lifecycle import (
    build_drain_result,
    build_restart_plan,
    build_rollback_plan,
    build_stop_result,
)
from nexus.mq.foundation_daemon_runtime import FoundationDaemonRuntime
from nexus.mq.foundation_daemon_status import build_foundation_daemon_status
from nexus.mq.message_contracts import build_execution_envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nexus.mq.foundation_daemon")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate-config",
        "status",
        "health",
        "readiness",
        "start-once",
        "run",
        "drain",
        "stop",
        "restart-plan",
        "rollback-plan",
    ):
        command = subcommands.add_parser(name)
        command.add_argument("--config", required=True)
        if name == "start-once":
            command.add_argument("--cycles", type=int, default=1)
        if name in {"drain", "stop"}:
            command.add_argument("--timeout", type=int, default=None)
    args = parser.parse_args(argv)

    try:
        config = load_foundation_daemon_config(args.config)
        payload = _handle(
            args.command,
            config,
            cycles=getattr(args, "cycles", None),
            timeout_seconds=getattr(args, "timeout", None),
        )
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        if args.command == "validate-config" and not payload.get("valid", False):
            return 2
        if args.command == "readiness" and not payload.get("overall_ready", False):
            return 2
        if args.command == "run" and payload.get("blocked", False):
            return 2
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "error": str(exc),
                    "not_business_completion": True,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 2


def _handle(
    command: str,
    config: dict[str, Any],
    *,
    cycles: int | None = None,
    timeout_seconds: int | None = None,
    adapter: Any | None = None,
) -> dict[str, Any]:
    if command == "validate-config":
        result = validate_foundation_daemon_config(config).to_dict()
        result["redacted_config"] = redact_config(config)
        return result
    if command in {"status", "health", "readiness"}:
        status = build_foundation_daemon_status(config=config)
        status["command"] = command
        return status
    if command == "start-once":
        if is_controlled_live_requested(config):
            return _run_controlled_live_diagnostic_command(
                config,
                command="start-once",
                cycles=cycles,
                adapter=adapter,
            )
        status = build_foundation_daemon_status(config=config)
        status.update(
            {
                "command": "start-once",
                "cycles_requested": cycles,
                "cycles_completed": 0,
                "daemon_started": False,
                "source_only_dry_run": True,
                "not_live_uat": True,
                "not_business_completion": True,
            }
        )
        return status
    if command == "run":
        if is_controlled_live_requested(config):
            return _run_controlled_live_diagnostic_command(config, command="run", adapter=adapter)
        status = build_foundation_daemon_status(config=config)
        status.update(
            {
                "command": "run",
                "blocked": True,
                "block_reason": "LIVE_DAEMON_RUN_NOT_AUTHORIZED_FOR_SOURCE_GATE",
                "daemon_started": False,
                "not_live_uat": True,
                "not_business_completion": True,
            }
        )
        return status
    if command == "drain":
        controlled_live = is_controlled_live_requested(config)
        result = build_drain_result(
            inflight_count=0,
            run_id=_controlled_live_run_id(config) if controlled_live else None,
            controlled_live=controlled_live,
        )
        result.update({"command": "drain", "timeout_seconds": timeout_seconds, "not_live_uat": not controlled_live})
        return result
    if command == "stop":
        result = build_stop_result(
            run_id=_controlled_live_run_id(config) if is_controlled_live_requested(config) else None,
            controlled_live=is_controlled_live_requested(config),
            timeout_seconds=timeout_seconds,
        )
        result["command"] = "stop"
        return result
    if command == "restart-plan":
        return build_restart_plan(config)
    if command == "rollback-plan":
        return build_rollback_plan(config)
    raise ValueError(f"UNSUPPORTED_COMMAND: {command}")


def _run_controlled_live_diagnostic_command(
    config: dict[str, Any],
    *,
    command: str,
    cycles: int | None = None,
    adapter: Any | None = None,
) -> dict[str, Any]:
    validation = validate_foundation_daemon_config(config)
    status = build_foundation_daemon_status(config=config)
    if not validation.valid:
        status.update(
            {
                "command": command,
                "blocked": True,
                "block_reason": validation.errors[0] if validation.errors else "CONTROLLED_LIVE_NOT_AUTHORIZED",
                "daemon_started": False,
                "controlled_live": True,
                "not_business_completion": True,
            }
        )
        return status

    runtime = None
    try:
        runtime = FoundationDaemonRuntime(
            config=config,
            adapter=adapter or _build_controlled_live_adapter(config),
            state_store=DurableStateStore(_durable_state_path(config)),
            evidence_root=_evidence_root(config),
        )
        result = runtime.run_controlled_live_diagnostic(_build_controlled_live_diagnostic_envelope(config))
    except Exception as exc:
        result = {
            "accepted": False,
            "errors": [f"CONTROLLED_LIVE_RUN_FAILED: {exc}"],
            "not_business_completion": True,
        }
    finally:
        if runtime is not None:
            try:
                runtime.close()
            except Exception:
                pass

    blocked = not result.get("accepted", False)
    payload = build_foundation_daemon_status(
        config=config,
        broker_ready=not blocked,
        jetstream_ready=not blocked,
        consumer_ready=not blocked,
    )
    payload.update(
        {
            "command": command,
            "blocked": blocked,
            "block_reason": (result.get("errors") or [None])[0] if blocked else None,
            "controlled_live": True,
            "daemon_started": not blocked,
            "cycles_requested": cycles,
            "cycles_completed": 1 if not blocked else 0,
            "result": result,
            "not_live_uat": False,
            "not_production_runtime": True,
            "not_business_completion": True,
        }
    )
    return payload


def _build_controlled_live_adapter(config: dict[str, Any]) -> Any:
    from nexus.mq.adapter_nats import MqAdapterNats

    broker = config.get("broker", {}) if isinstance(config, dict) else {}
    subjects = config.get("subjects", {}) if isinstance(config, dict) else {}
    urls = broker.get("urls") or []
    first_url = urls[0] if urls else ""
    stream_subjects = list(subjects.get("allowlist") or [])
    return MqAdapterNats(
        nats_url=str(first_url),
        subject_prefix=f"nexus.3_5.test.{CONTROLLED_LIVE_RUN_SCOPE}",
        stream_name=str(broker.get("stream", "")),
        dlq_stream_name=f"{broker.get('stream', 'NEXUS_3_5_WBS15_9_G6_20260607')}_DLQ",
        stream_subjects=stream_subjects,
        consumer_name=str(broker.get("consumer", "")),
        consumer_filter_subject=str(broker.get("filter_subject", "")),
        allow_broker_setup=False,
    )


def _build_controlled_live_diagnostic_envelope(config: dict[str, Any]) -> dict[str, Any]:
    controlled_live = config.get("controlled_live", {}) if isinstance(config, dict) else {}
    broker = config.get("broker", {}) if isinstance(config, dict) else {}
    run_id = _controlled_live_run_id(config)
    subject = str(broker.get("filter_subject", f"nexus.3_5.test.{run_id}.inbox"))
    envelope = build_execution_envelope(
        message_type="Command_Message",
        workflow_instance_id=run_id,
        workflow_type="controlled_3_5_uat",
        workflow_version="15.9",
        producer="thunder",
        payload={
            "command_name": "foundation_controlled_live_diagnostic",
            "target_handler": "layer3.foundation.diagnostic_loopback",
            "input_refs": [f"authority://{controlled_live.get('run_packet_ref', '')}"],
            "expected_outputs": ["transport_evidence", "result_candidate"],
            "allowed_side_effects": [],
            "commit_pattern": "local_transactional_default",
            "completion_event_type": "controlled_live_diagnostic_result",
        },
        idempotency_key=f"idem-{run_id}",
    ).to_dict()
    envelope["message_id"] = f"msg-{run_id}"
    envelope["subject"] = subject
    return envelope


def _controlled_live_run_id(config: dict[str, Any]) -> str:
    controlled_live = config.get("controlled_live", {}) if isinstance(config, dict) else {}
    return str(controlled_live.get("run_id") or CONTROLLED_LIVE_RUN_SCOPE)


def _durable_state_path(config: dict[str, Any]) -> Path:
    stores = config.get("stores", {}) if isinstance(config, dict) else {}
    durable = stores.get("durable_state", {}) if isinstance(stores, dict) else {}
    return _path_from_dsn(str(durable.get("dsn", f"sqlite:///tmp/{CONTROLLED_LIVE_RUN_SCOPE}/foundation.sqlite3")))


def _evidence_root(config: dict[str, Any]) -> Path:
    stores = config.get("stores", {}) if isinstance(config, dict) else {}
    evidence = stores.get("evidence", {}) if isinstance(stores, dict) else {}
    return _path_from_dsn(str(evidence.get("dsn", f"file://tmp/{CONTROLLED_LIVE_RUN_SCOPE}/evidence")))


def _path_from_dsn(dsn: str) -> Path:
    for prefix in ("sqlite:///", "file://"):
        if dsn.startswith(prefix):
            return Path(dsn[len(prefix) :])
    return Path(dsn)


if __name__ == "__main__":
    sys.exit(main())
