"""CLI for source-only Layer 3 MQ foundation daemon surfaces."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from nexus.mq.foundation_daemon_config import (
    load_foundation_daemon_config,
    redact_config,
    validate_foundation_daemon_config,
)
from nexus.mq.foundation_daemon_lifecycle import build_drain_result, build_restart_plan, build_rollback_plan
from nexus.mq.foundation_daemon_status import build_foundation_daemon_status


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
        result = build_drain_result(inflight_count=0)
        result.update({"command": "drain", "timeout_seconds": timeout_seconds, "not_live_uat": True})
        return result
    if command == "stop":
        return {
            "command": "stop",
            "timeout_seconds": timeout_seconds,
            "daemon_started": False,
            "offline": True,
            "source_only_no_process_signal_sent": True,
            "not_live_uat": True,
            "not_business_completion": True,
        }
    if command == "restart-plan":
        return build_restart_plan(config)
    if command == "rollback-plan":
        return build_rollback_plan(config)
    raise ValueError(f"UNSUPPORTED_COMMAND: {command}")


if __name__ == "__main__":
    sys.exit(main())
