"""Resident controller CLI.

The WBS 7.19.14.3 CLI is intentionally source-only and default-off. It exposes
validation/status command names without installing or starting a daemon.
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

from nexus.mq.resident_controller.service import build_status_snapshot


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WBS 7.19.14 resident controller source-only CLI")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("validate-config")
    subparsers.add_parser("status")
    subparsers.add_parser("start-once")
    subparsers.add_parser("drain")
    subparsers.add_parser("recover")
    subparsers.add_parser("build-evidence-package")
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_usage()
        return 2
    if args.command == "status":
        print(
            json.dumps(
                build_status_snapshot(
                    service_state="disabled",
                    broker_connected=False,
                    subscriptions_ready=False,
                    last_heartbeat_at="",
                    pending_assignments=[],
                    evidence_root="",
                ),
                sort_keys=True,
            )
        )
        return 0
    if args.command in {"validate-config", "build-evidence-package"}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
