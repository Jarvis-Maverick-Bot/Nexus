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
from nexus.mq.foundation_daemon_lifecycle import build_restart_plan, build_rollback_plan
from nexus.mq.foundation_daemon_status import build_foundation_daemon_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m nexus.mq.foundation_daemon")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-config", "status", "health", "readiness", "start-once", "restart-plan", "rollback-plan"):
        command = subcommands.add_parser(name)
        command.add_argument("--config", required=True)
        if name == "start-once":
            command.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args(argv)

    try:
        config = load_foundation_daemon_config(args.config)
        payload = _handle(args.command, config, cycles=getattr(args, "cycles", None))
        print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        if args.command == "validate-config" and not payload.get("valid", False):
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


def _handle(command: str, config: dict[str, Any], *, cycles: int | None = None) -> dict[str, Any]:
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
    if command == "restart-plan":
        return build_restart_plan(config)
    if command == "rollback-plan":
        return build_rollback_plan(config)
    raise ValueError(f"UNSUPPORTED_COMMAND: {command}")


if __name__ == "__main__":
    sys.exit(main())
