"""Resident controller CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional
import yaml

from nexus.mq.resident_controller.config import validate_resident_controller_config
from nexus.mq.resident_controller.evidence import ResidentEvidenceRecord, build_evidence_package
from nexus.mq.resident_controller.live_loop import run_start_once
from nexus.mq.resident_controller.recovery import ResidentControllerCheckpoint, classify_restart_recovery
from nexus.mq.resident_controller.service import (
    BrokerReadinessSnapshot,
    ResidentControllerService,
    ResidentControllerServicePolicy,
    build_drain_offline_record,
    build_status_snapshot,
)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WBS 7.19.14 resident controller source-only CLI")
    subparsers = parser.add_subparsers(dest="command")
    validate_parser = subparsers.add_parser("validate-config")
    validate_parser.add_argument("--config", required=True)
    validate_parser.add_argument("--output")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--output")
    start_parser = subparsers.add_parser("start-once")
    start_parser.add_argument("--config", required=True)
    start_parser.add_argument("--broker-readiness")
    start_parser.add_argument("--output")
    drain_parser = subparsers.add_parser("drain")
    drain_parser.add_argument("--run-id", required=True)
    drain_parser.add_argument("--reason-ref", required=True)
    drain_parser.add_argument("--output")
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("--checkpoint", required=True)
    recover_parser.add_argument("--output")
    evidence_parser = subparsers.add_parser("build-evidence-package")
    evidence_parser.add_argument("--run-id", required=True)
    evidence_parser.add_argument("--evidence-root", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if not args.command:
        parser.print_usage()
        return 2
    if args.command == "validate-config":
        config = _load_config(Path(args.config))
        result = validate_resident_controller_config(config)
        payload = {
            "valid": result.valid,
            "fail_closed": result.fail_closed,
            "errors": result.errors,
            "warnings": result.warnings,
            "config_hash": result.config_hash,
            "redacted_snapshot": result.redacted_snapshot,
            "live_runtime_allowed": result.live_runtime_allowed,
            "not_business_completion": result.not_business_completion,
        }
        _emit_json(payload, output=getattr(args, "output", None))
        return 0 if result.valid else 1
    if args.command == "status":
        _emit_json(
            build_status_snapshot(
                service_state="disabled",
                broker_connected=False,
                subscriptions_ready=False,
                last_heartbeat_at="",
                pending_assignments=[],
                evidence_root="",
            ),
            output=getattr(args, "output", None),
        )
        return 0
    if args.command == "start-once":
        config = _load_config(Path(args.config))
        if not args.broker_readiness:
            decision = run_start_once(config=config)
            _emit_json(
                {
                    "accepted": decision.accepted,
                    "daemon_started": decision.daemon_started,
                    "service_state": decision.service_state,
                    "errors": decision.errors,
                    "evidence_records": [record.to_dict() for record in decision.evidence_records],
                    "status_snapshot": decision.status_snapshot,
                    "evidence_package": {
                        "review_ready": decision.evidence_package.review_ready if decision.evidence_package else False,
                        "manifest_path": str(decision.evidence_package.manifest_path) if decision.evidence_package else "",
                        "checksum_path": str(decision.evidence_package.checksum_path) if decision.evidence_package else "",
                        "secret_scan_path": str(decision.evidence_package.secret_scan_path) if decision.evidence_package else "",
                    },
                    "not_business_completion": decision.not_business_completion,
                },
                output=getattr(args, "output", None),
            )
            return 0 if decision.accepted else 1
        broker_payload = json.loads(Path(args.broker_readiness).read_text(encoding="utf-8"))
        controller = dict(config.get("controller") or {})
        service = ResidentControllerService(
            policy=ResidentControllerServicePolicy(
                default_enabled=controller.get("launch_mode") == "bounded_uat",
                uat_authorized=bool(controller.get("run_authorization_ref")),
            )
        )
        decision = service.evaluate_start_once(
            config=config,
            broker=BrokerReadinessSnapshot(
                connected=bool(broker_payload.get("connected")),
                subscriptions_ready=bool(broker_payload.get("subscriptions_ready")),
                errors=list(broker_payload.get("errors") or []),
            ),
            run_authorization_ref=str(controller.get("run_authorization_ref") or ""),
        )
        _emit_json(
            {
                "accepted": decision.accepted,
                "daemon_started": decision.daemon_started,
                "service_state": decision.service_state,
                "errors": decision.errors,
                "evidence_records": [record.to_dict() for record in decision.evidence_records],
                "not_business_completion": decision.not_business_completion,
            },
            output=getattr(args, "output", None),
        )
        return 0 if decision.accepted else 1
    if args.command == "drain":
        _emit_json(
            build_drain_offline_record(
                run_id=args.run_id,
                reason_ref=args.reason_ref,
                connected=False,
                event_time="source-only",
            ),
            output=getattr(args, "output", None),
        )
        return 0
    if args.command == "recover":
        payload = json.loads(Path(args.checkpoint).read_text(encoding="utf-8"))
        result = classify_restart_recovery(
            ResidentControllerCheckpoint(
                run_id=payload.get("run_id", ""),
                service_state=payload.get("service_state", ""),
                pending_assignments=dict(payload.get("pending_assignments") or {}),
                completed_assignments=dict(payload.get("completed_assignments") or {}),
                replay_allowed=bool(payload.get("replay_allowed")),
            )
        )
        _emit_json(
            {
                "classifications": result.classifications,
                "replay_allowed": result.replay_allowed,
                "errors": result.errors,
                "not_business_completion": result.not_business_completion,
            },
            output=getattr(args, "output", None),
        )
        return 0 if not result.errors else 1
    if args.command == "build-evidence-package":
        result = build_evidence_package(
            run_id=args.run_id,
            evidence_root=Path(args.evidence_root),
            records=[
                ResidentEvidenceRecord(
                    sequence=1,
                    record_type="status",
                    event_time="source-only",
                    payload={
                        "service_state": "review_ready",
                        "not_business_completion": True,
                    },
                )
            ],
            status_summary={"service_state": "review_ready", "not_business_completion": True},
        )
        return 0
    return 2


def _load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise ValueError("CONFIG_FILE_MUST_BE_MAPPING")
        return loaded
    raise ValueError("ONLY_JSON_CONFIG_SUPPORTED_BY_SOURCE_CLI")


def _emit_json(payload: dict, *, output: Optional[str]) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    raise SystemExit(main())
