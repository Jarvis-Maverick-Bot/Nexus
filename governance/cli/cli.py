# governance/cli/cli.py
# Unified CLI entry point — Category A (governance/record), B (execution/dispatch), C (observation)
# Usage: python governance/cli/cli.py <command> [args]

import sys
import json

# Add parent to path for imports
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from governance.cli.store import (
    create_work_item, submit_artifact, request_transition,
    record_validation, signal_blocker, package_delivery, get_item
)
from governance.routing.engine import route_event, get_event_log
from governance.control.control import (
    launch_subagent, pause_task, resume_task, terminate_task,
    invoke_command, inspect_task, get_task_result, get_task_log
)


COMMANDS = {
    # Category A: Governance / Record
    "create-work-item":    (create_work_item,    "<name>"),
    "submit-artifact":     (submit_artifact,     "<item_id> <path>"),
    "request-transition":  (request_transition,  "<item_id> <stage>"),
    "record-validation":   (record_validation,   "<item_id> <pass|fail>"),
    "signal-blocker":      (signal_blocker,      "<item_id> <description>"),
    "package-delivery":    (package_delivery,     "<item_id>"),
    # Category C: Observation / Result
    "status":              (get_item,             "[item_id]"),
    # Category B: Execution / Dispatch
    "launch-subagent":     (launch_subagent,      "<task_id> <agent_type>"),
    "pause-task":          (pause_task,           "<task_id>"),
    "resume-task":         (resume_task,          "<task_id>"),
    "terminate-task":      (terminate_task,       "<task_id>"),
    "invoke-command":      (invoke_command,        "<task_id> <command>"),
    # Category C: Observation / Result
    "route-event":         (route_event,          "<json_string>"),
    "event-log":           (get_event_log,        "[event_id]"),
    "inspect-task":        (inspect_task,          "<task_id>"),
    "get-task-result":     (get_task_result,       "<task_id>"),
    "task-log":            (get_task_log,          ""),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--help" or sys.argv[1] == "-h":
        print("Governance CLI — V1.8")
        print()
        print("=== Category A: Governance / Record ===")
        for cmd in ["create-work-item", "submit-artifact", "request-transition",
                    "record-validation", "signal-blocker", "package-delivery"]:
            fn, usage = COMMANDS[cmd]
            print(f"  governance {cmd} {usage}")
        print()
        print("=== Category B: Execution / Dispatch ===")
        for cmd in ["launch-subagent", "invoke-command", "pause-task", "resume-task", "terminate-task"]:
            fn, usage = COMMANDS[cmd]
            print(f"  governance {cmd} {usage}")
        print()
        print("=== Category C: Observation / Result ===")
        for cmd in ["status", "route-event", "event-log", "inspect-task", "get-task-result", "task-log"]:
            fn, usage = COMMANDS[cmd]
            print(f"  governance {cmd} {usage}")
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
    elif cmd == "route-event":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "event-log":
        result = fn(args[0] if args else None)
    elif cmd == "launch-subagent":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], args[1])
    elif cmd == "pause-task":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "resume-task":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "terminate-task":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "invoke-command":
        if len(args) < 2:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0], " ".join(args[1:]))
    elif cmd == "inspect-task":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "get-task-result":
        if len(args) < 1:
            print(json.dumps({"error": f"EXPECTED: {usage}"})); sys.exit(1)
        result = fn(args[0])
    elif cmd == "task-log":
        result = fn()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
