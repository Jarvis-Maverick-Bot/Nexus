"""Module CLI for Candidate Adapter source-only operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from nexus.mq.candidate_adapter_api import (
    CandidateAdapterApi,
    CandidateAdapterProviders,
    InMemoryAssignmentBroker,
    InMemoryLifecycleProvider,
)
from nexus.mq.candidate_adapter_assignment_validator import CandidateAssignmentEvent
from nexus.mq.candidate_adapter_session_store import CandidateAdapterSessionStore


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Candidate Adapter source-only CLI")
    subparsers = parser.add_subparsers(dest="command")

    connect = subparsers.add_parser("connect")
    connect.add_argument("--profile", required=True)
    connect.add_argument("--session", required=True)
    connect.add_argument("--local-only-authorization", action="store_true")

    for name in ("register", "ready", "heartbeat", "await-assignment", "ack", "progress", "evidence", "result", "drain", "offline"):
        command = subparsers.add_parser(name)
        command.add_argument("--session", required=True)
        if name == "ready":
            command.add_argument("--startup-packet-ref", required=True)
            command.add_argument("--self-check-evidence-ref", required=True)
        elif name == "heartbeat":
            command.add_argument("--sequence", required=True, type=int)
            command.add_argument("--runtime-instance-id")
        elif name == "ack":
            command.add_argument("--assignment-json", required=True)
        elif name in {"progress", "evidence", "result"}:
            command.add_argument("--assignment-id", required=True)
            if name == "progress":
                command.add_argument("--progress-ref", required=True)
            elif name == "evidence":
                command.add_argument("--evidence-ref", required=True)
            else:
                command.add_argument("--result-ref", required=True)
                command.add_argument("--evidence-ref", required=True)
        elif name == "drain":
            command.add_argument("--reason-ref", required=True)
            command.add_argument("--evidence-ref", required=True)
        elif name == "offline":
            command.add_argument("--final-evidence-ref", required=True)
            command.add_argument("--reason-ref", default="source-only-shutdown")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_usage()
        return 2

    api = CandidateAdapterApi(
        session_store=CandidateAdapterSessionStore(getattr(args, "session", "candidate-session.json")),
        providers=CandidateAdapterProviders(
            broker=InMemoryAssignmentBroker(),
            lifecycle=InMemoryLifecycleProvider(),
        ),
    )
    try:
        result = _dispatch(api, args)
    except FileNotFoundError as exc:
        _emit({"accepted": False, "operation": args.command, "errors": [f"FILE_NOT_FOUND: {exc.filename}"]})
        return 1
    except ValueError as exc:
        _emit({"accepted": False, "operation": args.command, "errors": [str(exc)]})
        return 1
    _emit(result.to_dict())
    return 0 if result.accepted else 1


def _dispatch(api: CandidateAdapterApi, args: argparse.Namespace):
    if args.command == "connect":
        return api.connect(
            Path(args.profile),
            session_path=Path(args.session),
            local_only_authorization=bool(args.local_only_authorization),
        )
    if args.command == "register":
        return api.register(Path(args.session))
    if args.command == "ready":
        return api.submit_readiness(
            Path(args.session),
            startup_packet_ref=args.startup_packet_ref,
            self_check_evidence_ref=args.self_check_evidence_ref,
        )
    if args.command == "heartbeat":
        observed_state = {"runtime_instance_id": args.runtime_instance_id} if args.runtime_instance_id else None
        return api.heartbeat(Path(args.session), sequence=args.sequence, observed_state=observed_state)
    if args.command == "await-assignment":
        return api.await_assignment(Path(args.session))
    if args.command == "ack":
        assignment = CandidateAssignmentEvent.from_dict(json.loads(Path(args.assignment_json).read_text(encoding="utf-8")))
        return api.ack_assignment(Path(args.session), assignment)
    if args.command == "progress":
        return api.report_progress(Path(args.session), assignment_id=args.assignment_id, progress_ref=args.progress_ref)
    if args.command == "evidence":
        return api.report_evidence(Path(args.session), assignment_id=args.assignment_id, evidence_ref=args.evidence_ref)
    if args.command == "result":
        return api.report_result_candidate(
            Path(args.session),
            assignment_id=args.assignment_id,
            result_ref=args.result_ref,
            evidence_ref=args.evidence_ref,
        )
    if args.command == "drain":
        return api.drain(Path(args.session), reason_ref=args.reason_ref, evidence_ref=args.evidence_ref)
    if args.command == "offline":
        return api.offline(Path(args.session), final_evidence_ref=args.final_evidence_ref, reason_ref=args.reason_ref)
    raise ValueError(f"UNSUPPORTED_COMMAND: {args.command}")


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
