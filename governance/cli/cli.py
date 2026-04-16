# governance/cli/cli.py
# Unified CLI entry point — Category A (governance/record), B (observation)
# Usage: python governance/cli/cli.py <command> [args]

import sys
import json
from pathlib import Path

# Add repo root to path for imports (go up 3 levels from cli/cli.py to repo root)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from governance.cli.store import (
    create_work_item, submit_artifact, request_transition,
    record_validation, package_delivery, get_item
)
from governance.cli.commands.queue_cmd import queue_list
from governance.cli.commands.task_cmd import task_list
from governance.escalation.triggers import escalate as escalation_trigger


def do_signal_blocker(item_id: str, description: str) -> dict:
    """
    Signal a blocker against a work-item — routes to FB4 escalation system.

    Per Execution Plan V0.4: signal-blocker replaces V1.8 store-based
    blocker recording with FB4 escalation triggers.

    This creates an escalation record and publishes to NATS (gov.escalations).
    """
    escalation = escalation_trigger(
        item_id=item_id,
        reason=f"blocker_signal: {description}",
        context={
            "escalated_by": "operator",
            "escalation_reason": "blocker_signal",
            "blocker": {
                "description": description,
                "severity": "medium",  # default severity for operator-signal
            },
        },
    )
    return {
        "ok": True,
        "blocker_id": escalation.escalation_id,
        "item_id": item_id,
        "description": description,
        "escalation_state": escalation.state.value if hasattr(escalation.state, "value") else str(escalation.state),
    }


COMMANDS = {
    # Category A: Governance / Record
    "create-work-item":    (create_work_item,    "<name>"),
    "submit-artifact":     (submit_artifact,     "<item_id> <path>"),
    "request-transition":  (request_transition,  "<item_id> <stage>"),
    "record-validation":   (record_validation,   "<item_id> <pass|fail>"),
    "signal-blocker":      (do_signal_blocker,    "<item_id> <description>"),
    "package-delivery":    (package_delivery,     "<item_id>"),
    # Category B: Queue / Task Observation
    "queue-list":          (queue_list,          ""),
    "task-list":           (task_list,           ""),
    # Category C: Observation / Result
    "status":              (get_item,             "[item_id]"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--help" or sys.argv[1] == "-h":
        print("Governance CLI - V1.9")
        print()
        print("=== Category A: Governance / Record ===")
        for cmd in ["create-work-item", "submit-artifact", "request-transition",
                    "record-validation", "signal-blocker", "package-delivery"]:
            fn, usage = COMMANDS[cmd]
            print(f"  governance {cmd} {usage}")
        print()
        print("=== Category B: Queue / Task Observation ===")
        for cmd in ["queue-list", "task-list"]:
            fn, usage = COMMANDS[cmd]
            print(f"  governance {cmd} {usage}")
        print()
        print("=== Category C: Observation / Result ===")
        print("  governance status [item_id]")
        print()
        print("  governance --help")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(json.dumps({"error": f"Unknown command '{cmd}'", "valid": list(COMMANDS.keys())}, indent=2))
        sys.exit(1)

    fn, usage = COMMANDS[cmd]
    args = sys.argv[2:]

    if cmd == "create-work-item":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "submit-artifact":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "request-transition":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "record-validation":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "signal-blocker":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], " ".join(args[1:]))
    elif cmd == "package-delivery":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "status":
        result = fn(args[0] if args else None)
    elif cmd == "queue-list":
        result = fn()
    elif cmd == "task-list":
        result = fn()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()