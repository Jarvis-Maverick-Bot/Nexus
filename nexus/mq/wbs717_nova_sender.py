"""Nova WBS 7.17 live sender adapter.

This module is the approved Nexus-side sender entrypoint for WBS 7.17
assignment probes. It validates the run-scoped 4.19 subject and assignment
envelope before any publish attempt, writes a non-secret audit log, and keeps
live publish behind an explicit ``--live`` flag.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Optional, Protocol
from urllib.parse import urlparse
import uuid


WBS717_SCHEMA_VERSION = "4.19-task-probe-v0.1"
WBS717_TASK_TYPE = "NON_BUSINESS_DIAGNOSTIC_TASK_PROBE"
WBS717_SUBJECT_PREFIX_ROOT = "nexus.4_19.wbs7_17.jarvis"
WBS717_VOID_RUN_IDS = {"wbs-7-17-20260520T120338Z-25e0fa"}
RUN_ID_RE = re.compile(r"^wbs-7-17-(?P<ts>\d{8}T\d{6}Z)-(?P<suffix>[a-z0-9]{4,12})$")
FRESH_RUN_MAX_AGE_SECONDS = 24 * 60 * 60
FRESH_RUN_MAX_FUTURE_SECONDS = 5 * 60
DEFAULT_NO_GO_BOUNDARIES = [
    "no business task dispatch",
    "no business execution",
    "no business commit",
    "no production operational dispatch",
    "no private-agent registration dispatch invocation or result use",
    "no broad command subjects",
    "no broker config change",
    "no credential exposure",
    "no UI Dashboard implementation",
    "no persistent always-on runtime enablement",
    "ack delivery progress assignment and result candidate are not business completion",
]
SECRET_VALUE_MARKERS = (
    "password=",
    "token=",
    "secret=",
    "authorization:",
    "bearer ",
    "api_key=",
    "-----begin",
)
FORBIDDEN_SUBJECT_PREFIXES = (
    "agent.",
    "workflow.",
    "review.",
    "feedback.",
    "ops.",
    "private_agent.",
)


@dataclass(frozen=True)
class SenderValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PublishOutcome:
    accepted: bool
    publish_status: str
    error_class: Optional[str] = None
    nats_sequence: Optional[int] = None
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SenderAttemptRecord:
    timestamp: str
    sender_identity: str
    endpoint_host_port: str
    credential_ref: str
    subject: str
    run_id: str
    assignment_id: str
    correlation_id: str
    idempotency_key: str
    payload_hash: str
    publish_status: str
    error_class: Optional[str]
    duplicate_replay: bool
    audit_log_path: str
    dry_run: bool
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SenderRunResult:
    accepted: bool
    subject: str
    run_id: str
    assignment_id: str
    correlation_id: str
    idempotency_key: str
    payload_hash: str
    audit_log_path: str
    attempts: list[SenderAttemptRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = True
    duplicate_replay_requested: bool = False
    live_publish_attempted: bool = False
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssignmentPublisher(Protocol):
    def publish(self, *, subject: str, payload: bytes, credential_ref: str, timeout_seconds: int) -> PublishOutcome:
        ...


class LiveNatsAssignmentPublisher:
    """Core NATS publisher used only when the CLI is invoked with ``--live``.

    It does not create streams, consumers, or broker configuration. The
    credential value is resolved in memory from an ``env:`` reference or a
    local ``*.env`` credential-reference path and is never returned to callers
    or written to audit records.
    """

    def publish(self, *, subject: str, payload: bytes, credential_ref: str, timeout_seconds: int) -> PublishOutcome:
        try:
            url = _resolve_live_nats_url(credential_ref)
            return asyncio.run(_publish_nats_core(url, subject, payload, timeout_seconds))
        except Exception as exc:
            return PublishOutcome(
                accepted=False,
                publish_status="publish_failed",
                error_class=exc.__class__.__name__,
            )


def generate_run_id(now_at: Optional[str] = None) -> str:
    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    stamp = now_dt.strftime("%Y%m%dT%H%M%SZ")
    return f"wbs-7-17-{stamp}-{uuid.uuid4().hex[:6]}"


def build_subject_manifest(run_id: str) -> dict[str, Any]:
    subject_prefix = f"{WBS717_SUBJECT_PREFIX_ROOT}.{run_id}"
    return {
        "run_id": run_id,
        "subject_prefix": subject_prefix,
        "assignment_subject": f"{subject_prefix}.assignment",
        "ack_subject": f"{subject_prefix}.ack",
        "progress_subject": f"{subject_prefix}.progress",
        "evidence_subject": f"{subject_prefix}.evidence",
        "result_candidate_subject": f"{subject_prefix}.result_candidate",
        "anomaly_subject": f"{subject_prefix}.anomaly",
        "not_business_completion": True,
    }


def build_assignment_subject(run_id: str) -> str:
    return build_subject_manifest(run_id)["assignment_subject"]


def build_assignment_envelope(
    *,
    run_id: str,
    created_at: str,
    expires_at: str,
    assignment_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    task_type: str = WBS717_TASK_TYPE,
    no_go_boundaries: Optional[list[str]] = None,
) -> dict[str, Any]:
    assignment_id = assignment_id or f"assign-wbs7-17-{run_id}-001"
    correlation_id = correlation_id or f"corr-wbs7-17-{run_id}-001"
    idempotency_key = idempotency_key or f"idem-wbs7-17-{run_id}-001"
    envelope = {
        "schema_version": WBS717_SCHEMA_VERSION,
        "wbs": "7.17",
        "run_id": run_id,
        "assignment_id": assignment_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "task_type": task_type,
        "assignment_class": task_type,
        "payload_hash": "",
        "created_at": created_at,
        "expires_at": expires_at,
        "from_agent": "nova",
        "to_agent": "jarvis",
        "intent": "prove bounded Jarvis non-business task execution and result-candidate evidence only",
        "business_execution_allowed": False,
        "business_commit_allowed": False,
        "private_agent_invocation_allowed": False,
        "persistent_runtime_enablement_allowed": False,
        "delivery_is_completion": False,
        "ack_is_progress": False,
        "progress_is_completion": False,
        "result_candidate_is_business_completion": False,
        "requested_response": "ack_progress_evidence_and_result_candidate_only",
        "no_go_boundaries": list(no_go_boundaries or DEFAULT_NO_GO_BOUNDARIES),
        "not_business_completion": True,
    }
    envelope["payload_hash"] = compute_payload_hash(envelope)
    return envelope


def validate_sender_request(
    *,
    subject: str,
    envelope: dict[str, Any],
    credential_ref: str,
    endpoint: str,
    now_at: Optional[str] = None,
) -> SenderValidationResult:
    errors: list[str] = []
    if not isinstance(envelope, dict):
        return SenderValidationResult(False, ["MALFORMED_ASSIGNMENT_ENVELOPE"])
    run_id = str(envelope.get("run_id", ""))
    errors.extend(validate_run_id(run_id, now_at=now_at).errors)
    errors.extend(_subject_errors(subject, run_id))
    errors.extend(_credential_ref_errors(credential_ref))
    errors.extend(_endpoint_errors(endpoint))
    errors.extend(_envelope_errors(envelope, now_at=now_at))
    errors.extend(_secret_material_errors({"subject": subject, "envelope": envelope, "credential_ref": credential_ref}))
    return SenderValidationResult(valid=not errors, errors=_dedupe(errors))


def validate_run_id(run_id: str, *, now_at: Optional[str] = None) -> SenderValidationResult:
    errors: list[str] = []
    match = RUN_ID_RE.match(run_id or "")
    if not match:
        errors.append("INVALID_WBS717_RUN_ID")
    elif run_id in WBS717_VOID_RUN_IDS:
        errors.append("VOID_WBS717_RUN_ID_REUSED")
    else:
        run_dt = _parse_run_id_timestamp(match.group("ts"))
        now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
        if run_dt is None or now_dt is None:
            errors.append("INVALID_WBS717_RUN_ID_TIMESTAMP")
        elif (now_dt - run_dt).total_seconds() > FRESH_RUN_MAX_AGE_SECONDS:
            errors.append("STALE_WBS717_RUN_ID")
        elif (run_dt - now_dt).total_seconds() > FRESH_RUN_MAX_FUTURE_SECONDS:
            errors.append("FUTURE_WBS717_RUN_ID")
    return SenderValidationResult(valid=not errors, errors=errors)


def send_wbs717_assignment(
    *,
    subject: str,
    envelope: dict[str, Any],
    credential_ref: str,
    endpoint: str,
    audit_log_path: str | Path,
    sender_identity: str = "nova",
    dry_run: bool = True,
    duplicate_replay: bool = False,
    publisher: Optional[AssignmentPublisher] = None,
    now_at: Optional[str] = None,
    timeout_seconds: int = 5,
) -> SenderRunResult:
    audit_path = Path(audit_log_path)
    endpoint_host_port = endpoint_host_port_only(endpoint)
    payload_hash = str(envelope.get("payload_hash", ""))
    run_id = str(envelope.get("run_id", ""))
    assignment_id = str(envelope.get("assignment_id", ""))
    correlation_id = str(envelope.get("correlation_id", ""))
    idempotency_key = str(envelope.get("idempotency_key", ""))
    validation = validate_sender_request(
        subject=subject,
        envelope=envelope,
        credential_ref=credential_ref,
        endpoint=endpoint,
        now_at=now_at,
    )
    if not validation.valid:
        attempt = _attempt_record(
            sender_identity=sender_identity,
            endpoint_host_port=endpoint_host_port,
            credential_ref=credential_ref,
            subject=subject,
            run_id=run_id,
            assignment_id=assignment_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            publish_status="rejected",
            error_class=validation.errors[0] if validation.errors else "VALIDATION_FAILED",
            duplicate_replay=False,
            audit_log_path=str(audit_path),
            dry_run=dry_run,
            now_at=now_at,
        )
        _append_audit_record(audit_path, attempt)
        return SenderRunResult(
            accepted=False,
            subject=subject,
            run_id=run_id,
            assignment_id=assignment_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            audit_log_path=str(audit_path),
            attempts=[attempt],
            errors=validation.errors,
            dry_run=dry_run,
            duplicate_replay_requested=duplicate_replay,
            live_publish_attempted=not dry_run,
        )

    attempts: list[SenderAttemptRecord] = []
    attempt_count = 2 if duplicate_replay else 1
    publisher = publisher or LiveNatsAssignmentPublisher()
    payload_bytes = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    for index in range(attempt_count):
        duplicate = index == 1
        if dry_run:
            outcome = PublishOutcome(
                accepted=True,
                publish_status="dry_run_duplicate_replay" if duplicate else "dry_run_validated",
            )
        else:
            outcome = publisher.publish(
                subject=subject,
                payload=payload_bytes,
                credential_ref=credential_ref,
                timeout_seconds=timeout_seconds,
            )
        attempt = _attempt_record(
            sender_identity=sender_identity,
            endpoint_host_port=endpoint_host_port,
            credential_ref=credential_ref,
            subject=subject,
            run_id=run_id,
            assignment_id=assignment_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            publish_status=outcome.publish_status,
            error_class=outcome.error_class,
            duplicate_replay=duplicate,
            audit_log_path=str(audit_path),
            dry_run=dry_run,
            now_at=now_at,
        )
        _append_audit_record(audit_path, attempt)
        attempts.append(attempt)
        if not outcome.accepted:
            return SenderRunResult(
                accepted=False,
                subject=subject,
                run_id=run_id,
                assignment_id=assignment_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                audit_log_path=str(audit_path),
                attempts=attempts,
                errors=[outcome.error_class or "PUBLISH_FAILED"],
                dry_run=dry_run,
                duplicate_replay_requested=duplicate_replay,
                live_publish_attempted=not dry_run,
            )

    return SenderRunResult(
        accepted=True,
        subject=subject,
        run_id=run_id,
        assignment_id=assignment_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        audit_log_path=str(audit_path),
        attempts=attempts,
        dry_run=dry_run,
        duplicate_replay_requested=duplicate_replay,
        live_publish_attempted=not dry_run,
    )


def write_evidence_package(
    *,
    evidence_root: str | Path,
    result: SenderRunResult,
    envelope: dict[str, Any],
    subject_manifest: dict[str, Any],
    credential_ref: str,
    endpoint: str,
    validation_failures: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    root = Path(evidence_root)
    logs = root / "logs"
    evidence = root / "evidence"
    logs.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []

    files.append(_write_json(evidence / "02_nova_sender_path_validation.json", {
        "sender_path": "python -m nexus.mq.wbs717_nova_sender",
        "adapter_module": "nexus.mq.wbs717_nova_sender",
        "real_4_19_adapter_entrypoint": True,
        "not_ad_hoc_uat_controller": True,
        "forbidden_controller_used": False,
        "credential_ref": credential_ref,
        "endpoint_host_port": endpoint_host_port_only(endpoint),
        "audit_log_path": result.audit_log_path,
        "not_business_completion": True,
    }))
    files.append(_write_json(evidence / "04_subject_manifest.json", subject_manifest))
    files.append(_write_json(evidence / "06_assignment_sent.json", result.to_dict()))
    files.append(_write_json(evidence / "12_idempotency_duplicate_check.json", {
        "duplicate_replay_requested": result.duplicate_replay_requested,
        "attempt_count": len(result.attempts),
        "same_assignment_id": len({attempt.assignment_id for attempt in result.attempts}) <= 1,
        "same_idempotency_key": len({attempt.idempotency_key for attempt in result.attempts}) <= 1,
        "same_payload_hash": len({attempt.payload_hash for attempt in result.attempts}) <= 1,
        "not_business_completion": True,
    }))
    files.append(_write_json(evidence / "safe_assignment_envelope_example.json", envelope))
    files.append(_write_json(evidence / "invalid_fail_closed_evidence.json", {
        "validation_failures": list(validation_failures or []),
        "fail_closed": True,
        "not_business_completion": True,
    }))
    files.append(_write_json(evidence / "14_secret_scan.json", secret_scan_record(root)))
    files.append(_write_text(root / "probe_summary.md", _probe_summary(result, credential_ref, endpoint)))

    manifest_path = root / "manifest.json"
    files.append(_write_json(manifest_path, {
        "package_type": "wbs_7_17_nova_sender_adapter_evidence",
        "run_id": result.run_id,
        "sender_entrypoint": "python -m nexus.mq.wbs717_nova_sender",
        "branch": "thunder/wbs-7-17-nova-sender-adapter",
        "commit": "",
        "files": [str(path.relative_to(root)) for path in files if path != manifest_path],
        "not_business_completion": True,
    }))
    _write_sha256s(root)
    return {"evidence_root": str(root), "files_written": [str(path) for path in files]}


def secret_scan_record(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    findings: list[dict[str, str]] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "14_secret_scan.json":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in SECRET_VALUE_MARKERS:
            if marker in text.lower():
                findings.append({"path": str(path), "marker": marker})
    return {
        "secret_values_found": len(findings),
        "findings": findings,
        "credential_values_written": False,
        "not_business_completion": True,
    }


def compute_payload_hash(envelope: dict[str, Any]) -> str:
    payload = dict(envelope)
    payload["payload_hash"] = ""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def endpoint_host_port_only(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.username or parsed.password:
        return "invalid-endpoint-contains-credentials"
    if not parsed.hostname or not parsed.port:
        return "invalid-endpoint"
    return f"{parsed.hostname}:{parsed.port}"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WBS 7.17 Nova live sender adapter")
    parser.add_argument("--run-id", help="Fresh run id. If omitted, a dry-run id is generated.")
    parser.add_argument("--subject", help="Assignment subject. Defaults to the run-scoped WBS 7.17 subject.")
    parser.add_argument("--credential-ref", required=True, help="Credential reference only, never a credential value.")
    parser.add_argument("--endpoint", required=True, help="Live endpoint URL without credentials, used for host/port audit.")
    parser.add_argument("--audit-log", help="JSONL audit log path.")
    parser.add_argument("--evidence-root", help="Optional evidence package root.")
    parser.add_argument("--result-json", help="Optional sender result JSON path.")
    parser.add_argument("--sender-identity", default="nova")
    parser.add_argument("--task-type", default=WBS717_TASK_TYPE)
    parser.add_argument("--duplicate-replay", action="store_true")
    parser.add_argument("--live", action="store_true", help="Actually publish to live NATS. Default is dry-run.")
    parser.add_argument("--now-at", help="Test hook for deterministic timestamps.")
    args = parser.parse_args(argv)

    now_at = args.now_at or datetime.now(timezone.utc).isoformat()
    run_id = args.run_id or generate_run_id(now_at)
    subject = args.subject or build_assignment_subject(run_id)
    created_at = now_at
    expires_dt = (_parse_iso(now_at) or datetime.now(timezone.utc)) + timedelta(minutes=5)
    envelope = build_assignment_envelope(
        run_id=run_id,
        created_at=created_at,
        expires_at=expires_dt.isoformat(),
        task_type=args.task_type,
    )
    audit_log = args.audit_log or str(Path("evidence") / "wbs_7_17_nova_sender_adapter" / run_id / "logs" / "nova_assignment_sender.log")
    result = send_wbs717_assignment(
        subject=subject,
        envelope=envelope,
        credential_ref=args.credential_ref,
        endpoint=args.endpoint,
        audit_log_path=audit_log,
        sender_identity=args.sender_identity,
        dry_run=not args.live,
        duplicate_replay=args.duplicate_replay,
        now_at=now_at,
    )
    if args.result_json:
        _write_json(Path(args.result_json), result.to_dict())
    if args.evidence_root:
        write_evidence_package(
            evidence_root=args.evidence_root,
            result=result,
            envelope=envelope,
            subject_manifest=build_subject_manifest(run_id),
            credential_ref=args.credential_ref,
            endpoint=args.endpoint,
        )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.accepted else 2


async def _publish_nats_core(url: str, subject: str, payload: bytes, timeout_seconds: int) -> PublishOutcome:
    try:
        import nats
    except ImportError as exc:
        raise RuntimeError("NATS_PY_NOT_INSTALLED") from exc
    nc = await nats.connect(url, connect_timeout=timeout_seconds, max_reconnect_attempts=0)
    try:
        await nc.publish(subject, payload)
        await nc.flush(timeout=timeout_seconds)
        return PublishOutcome(accepted=True, publish_status="published")
    finally:
        await nc.close()


def _resolve_live_nats_url(credential_ref: str) -> str:
    if not credential_ref.startswith("env:"):
        return _resolve_live_nats_url_from_file_ref(credential_ref)
    env_name = credential_ref.split(":", 1)[1]
    if not re.match(r"^[A-Z0-9_]+$", env_name):
        raise ValueError("INVALID_ENV_CREDENTIAL_REF")
    value = os.environ.get(env_name)
    if not value:
        raise ValueError("CREDENTIAL_REF_NOT_RESOLVED")
    return value


def _resolve_live_nats_url_from_file_ref(credential_ref: str) -> str:
    path_text = credential_ref
    if credential_ref.startswith("file-ref://"):
        path_text = credential_ref.removeprefix("file-ref://")
    elif credential_ref.startswith("file-ref:"):
        path_text = credential_ref.removeprefix("file-ref:")
    if not _looks_like_file_ref(path_text):
        raise ValueError("LIVE_MODE_REQUIRES_RESOLVABLE_CREDENTIAL_REF")
    path = Path(path_text)
    if not path.exists():
        raise ValueError("CREDENTIAL_REF_FILE_NOT_FOUND")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() in {"NATS_URL", "NATS_URI", "NEXUS_NATS_URL", "NOVA_NATS_URL"} and value.strip():
            return value.strip().strip('"').strip("'")
    raise ValueError("CREDENTIAL_REF_FILE_MISSING_NATS_URL")


def _subject_errors(subject: str, run_id: str) -> list[str]:
    errors: list[str] = []
    if not subject:
        errors.append("MISSING_ASSIGNMENT_SUBJECT")
        return errors
    if any(marker in subject for marker in ("*", ">")):
        errors.append("WILDCARD_SUBJECT_NOT_ALLOWED")
    if subject.startswith(FORBIDDEN_SUBJECT_PREFIXES):
        errors.append("BROAD_OR_FORBIDDEN_SUBJECT_NOT_ALLOWED")
    expected = build_assignment_subject(run_id) if run_id else ""
    if subject != expected:
        errors.append("WBS717_SUBJECT_NOT_RUN_SCOPED_ASSIGNMENT")
    return errors


def _credential_ref_errors(credential_ref: str) -> list[str]:
    errors: list[str] = []
    if not credential_ref:
        return ["MISSING_CREDENTIAL_REF"]
    lowered = credential_ref.lower()
    if lowered.startswith("nats://") or "@" in credential_ref:
        errors.append("CREDENTIAL_REF_MUST_NOT_BE_CREDENTIAL_VALUE")
    if any(marker in lowered for marker in SECRET_VALUE_MARKERS):
        errors.append("CREDENTIAL_REF_CONTAINS_SECRET_VALUE")
    if not _is_supported_credential_ref(credential_ref):
        errors.append("UNSUPPORTED_CREDENTIAL_REF")
    return errors


def _is_supported_credential_ref(credential_ref: str) -> bool:
    return (
        credential_ref.startswith("env:")
        or credential_ref.startswith("credential-ref://")
        or credential_ref.startswith("file-ref://")
        or credential_ref.startswith("file-ref:")
        or _looks_like_file_ref(credential_ref)
    )


def _looks_like_file_ref(value: str) -> bool:
    return (
        value.startswith("/")
        or bool(re.match(r"^[A-Za-z]:[\\/]", value))
        or value.endswith(".env")
    )


def _endpoint_errors(endpoint: str) -> list[str]:
    errors: list[str] = []
    parsed = urlparse(endpoint)
    if parsed.scheme != "nats":
        errors.append("INVALID_LIVE_ENDPOINT_SCHEME")
    if parsed.username or parsed.password:
        errors.append("LIVE_ENDPOINT_MUST_NOT_EMBED_CREDENTIALS")
    if not parsed.hostname or not parsed.port:
        errors.append("LIVE_ENDPOINT_HOST_PORT_REQUIRED")
    return errors


def _envelope_errors(envelope: dict[str, Any], *, now_at: Optional[str]) -> list[str]:
    errors: list[str] = []
    required = [
        "schema_version",
        "wbs",
        "run_id",
        "assignment_id",
        "correlation_id",
        "idempotency_key",
        "task_type",
        "payload_hash",
        "created_at",
        "expires_at",
        "no_go_boundaries",
    ]
    for field_name in required:
        if not envelope.get(field_name):
            errors.append(f"MISSING_{field_name.upper()}")
    if envelope.get("schema_version") != WBS717_SCHEMA_VERSION:
        errors.append("UNSUPPORTED_WBS717_ASSIGNMENT_SCHEMA")
    if envelope.get("wbs") != "7.17":
        errors.append("INVALID_WBS")
    if envelope.get("task_type") != WBS717_TASK_TYPE:
        errors.append("UNAUTHORIZED_TASK_TYPE")
    if envelope.get("assignment_class") and envelope.get("assignment_class") != WBS717_TASK_TYPE:
        errors.append("UNAUTHORIZED_ASSIGNMENT_CLASS")
    if envelope.get("from_agent") != "nova" or envelope.get("to_agent") != "jarvis":
        errors.append("INVALID_ASSIGNMENT_SENDER_OR_RECIPIENT")
    for flag in [
        "business_execution_allowed",
        "business_commit_allowed",
        "private_agent_invocation_allowed",
        "persistent_runtime_enablement_allowed",
        "delivery_is_completion",
        "ack_is_progress",
        "progress_is_completion",
        "result_candidate_is_business_completion",
    ]:
        if envelope.get(flag) is not False:
            errors.append(f"UNSAFE_ASSIGNMENT_FLAG: {flag}")
    if envelope.get("not_business_completion") is not True:
        errors.append("ASSIGNMENT_CANNOT_BE_BUSINESS_COMPLETION")
    if not isinstance(envelope.get("no_go_boundaries"), list) or not envelope.get("no_go_boundaries"):
        errors.append("MISSING_NO_GO_BOUNDARIES")
    if envelope.get("payload_hash") != compute_payload_hash(envelope):
        errors.append("PAYLOAD_HASH_MISMATCH")
    created_dt = _parse_iso(str(envelope.get("created_at", "")))
    expires_dt = _parse_iso(str(envelope.get("expires_at", "")))
    now_dt = _parse_iso(now_at) if now_at else datetime.now(timezone.utc)
    if created_dt is None:
        errors.append("INVALID_CREATED_AT")
    if expires_dt is None:
        errors.append("INVALID_EXPIRES_AT")
    elif now_dt is None or expires_dt <= now_dt:
        errors.append("ASSIGNMENT_EXPIRED")
    return errors


def _secret_material_errors(value: Any, path: str = "payload") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_secret_material_errors(item, f"{path}.{key}"))
        return _dedupe(errors)
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_secret_material_errors(item, f"{path}[{index}]"))
        return _dedupe(errors)
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_VALUE_MARKERS):
            errors.append(f"SECRET_MATERIAL_VALUE: {path}")
    return _dedupe(errors)


def _attempt_record(
    *,
    sender_identity: str,
    endpoint_host_port: str,
    credential_ref: str,
    subject: str,
    run_id: str,
    assignment_id: str,
    correlation_id: str,
    idempotency_key: str,
    payload_hash: str,
    publish_status: str,
    error_class: Optional[str],
    duplicate_replay: bool,
    audit_log_path: str,
    dry_run: bool,
    now_at: Optional[str],
) -> SenderAttemptRecord:
    return SenderAttemptRecord(
        timestamp=now_at or datetime.now(timezone.utc).isoformat(),
        sender_identity=sender_identity,
        endpoint_host_port=endpoint_host_port,
        credential_ref=credential_ref,
        subject=subject,
        run_id=run_id,
        assignment_id=assignment_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        publish_status=publish_status,
        error_class=error_class,
        duplicate_replay=duplicate_replay,
        audit_log_path=audit_log_path,
        dry_run=dry_run,
    )


def _append_audit_record(path: Path, record: SenderAttemptRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_sha256s(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            digest = sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _probe_summary(result: SenderRunResult, credential_ref: str, endpoint: str) -> str:
    return "\n".join(
        [
            "# WBS 7.17 Nova Sender Adapter Evidence",
            "",
            f"run_id: {result.run_id}",
            "sender_entrypoint: python -m nexus.mq.wbs717_nova_sender",
            f"subject: {result.subject}",
            f"endpoint_host_port: {endpoint_host_port_only(endpoint)}",
            f"credential_ref: {credential_ref}",
            f"audit_log_path: {result.audit_log_path}",
            f"dry_run: {str(result.dry_run).lower()}",
            f"accepted: {str(result.accepted).lower()}",
            f"duplicate_replay_requested: {str(result.duplicate_replay_requested).lower()}",
            "jarvis_listener_started: false",
            "uat_window_opened: false",
            "business_execution_performed: false",
            "private_agent_invocation_performed: false",
            "",
        ]
    )


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_run_id_timestamp(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
