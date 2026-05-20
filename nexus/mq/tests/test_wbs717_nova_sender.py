import json
from datetime import datetime, timedelta, timezone

from nexus.mq.wbs717_nova_sender import (
    WBS717_TASK_TYPE,
    LiveNatsAssignmentPublisher,
    PublishOutcome,
    build_assignment_envelope,
    build_assignment_subject,
    build_subject_manifest,
    compute_payload_hash,
    endpoint_host_port_only,
    send_wbs717_assignment,
    validate_sender_request,
    write_evidence_package,
)


NOW = "2026-05-20T12:00:00+00:00"
RUN_ID = "wbs-7-17-20260520T120000Z-a1b2c3"
ENDPOINT = "nats://192.168.31.124:4222"
CREDENTIAL_REF = "credential-ref://nova/wbs-7-17/live-nats"


class FakePublisher:
    def __init__(self):
        self.calls = []

    def publish(self, *, subject, payload, credential_ref, timeout_seconds):
        self.calls.append(
            {
                "subject": subject,
                "payload": json.loads(payload.decode("utf-8")),
                "credential_ref": credential_ref,
                "timeout_seconds": timeout_seconds,
            }
        )
        return PublishOutcome(accepted=True, publish_status="published")


def _expires(minutes=5):
    return (datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _envelope(**overrides):
    envelope = build_assignment_envelope(
        run_id=RUN_ID,
        created_at=NOW,
        expires_at=_expires(),
    )
    envelope.update(overrides)
    if "payload_hash" not in overrides:
        envelope["payload_hash"] = compute_payload_hash(envelope)
    return envelope


def test_wbs717_subject_manifest_is_run_scoped_to_assignment_subject():
    manifest = build_subject_manifest(RUN_ID)

    assert manifest["subject_prefix"] == f"nexus.4_19.wbs7_17.jarvis.{RUN_ID}"
    assert manifest["assignment_subject"] == build_assignment_subject(RUN_ID)
    assert manifest["assignment_subject"].endswith(".assignment")
    assert ">" not in manifest["assignment_subject"]


def test_wbs717_assignment_envelope_contains_required_audit_and_idempotency_fields():
    envelope = _envelope()

    for field in [
        "run_id",
        "assignment_id",
        "correlation_id",
        "idempotency_key",
        "task_type",
        "payload_hash",
        "created_at",
        "expires_at",
        "no_go_boundaries",
    ]:
        assert envelope[field]
    assert envelope["task_type"] == WBS717_TASK_TYPE
    assert envelope["business_execution_allowed"] is False
    assert envelope["private_agent_invocation_allowed"] is False
    assert envelope["not_business_completion"] is True


def test_wbs717_sender_dry_run_writes_non_secret_audit_log_without_publishing(tmp_path):
    publisher = FakePublisher()
    audit = tmp_path / "nova_assignment_sender.log"

    result = send_wbs717_assignment(
        subject=build_assignment_subject(RUN_ID),
        envelope=_envelope(),
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=audit,
        dry_run=True,
        publisher=publisher,
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.attempts[0].publish_status == "dry_run_validated"
    assert result.attempts[0].endpoint_host_port == "192.168.31.124:4222"
    assert publisher.calls == []
    log_text = audit.read_text(encoding="utf-8")
    assert "credential-ref://nova/wbs-7-17/live-nats" in log_text
    assert "password=" not in log_text.lower()
    assert "token=" not in log_text.lower()


def test_wbs717_sender_live_path_uses_publisher_and_supports_one_duplicate_replay(tmp_path):
    publisher = FakePublisher()
    envelope = _envelope()

    result = send_wbs717_assignment(
        subject=build_assignment_subject(RUN_ID),
        envelope=envelope,
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=tmp_path / "sender.log",
        dry_run=False,
        duplicate_replay=True,
        publisher=publisher,
        now_at=NOW,
    )

    assert result.accepted is True
    assert result.live_publish_attempted is True
    assert len(publisher.calls) == 2
    assert publisher.calls[0]["subject"] == build_assignment_subject(RUN_ID)
    assert publisher.calls[0]["payload"]["idempotency_key"] == envelope["idempotency_key"]
    assert publisher.calls[1]["payload"]["idempotency_key"] == envelope["idempotency_key"]
    assert result.attempts[1].duplicate_replay is True


def test_wbs717_sender_rejects_invalid_subject_before_publish(tmp_path):
    publisher = FakePublisher()

    result = send_wbs717_assignment(
        subject="agent.jarvis.inbox",
        envelope=_envelope(),
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=tmp_path / "sender.log",
        dry_run=False,
        publisher=publisher,
        now_at=NOW,
    )

    assert result.accepted is False
    assert "BROAD_OR_FORBIDDEN_SUBJECT_NOT_ALLOWED" in result.errors
    assert "WBS717_SUBJECT_NOT_RUN_SCOPED_ASSIGNMENT" in result.errors
    assert result.attempts[0].publish_status == "rejected"
    assert publisher.calls == []


def test_wbs717_sender_rejects_invalid_task_type_before_publish(tmp_path):
    publisher = FakePublisher()

    result = send_wbs717_assignment(
        subject=build_assignment_subject(RUN_ID),
        envelope=_envelope(task_type="BUSINESS_TASK"),
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=tmp_path / "sender.log",
        dry_run=False,
        publisher=publisher,
        now_at=NOW,
    )

    assert result.accepted is False
    assert "UNAUTHORIZED_TASK_TYPE" in result.errors
    assert publisher.calls == []


def test_wbs717_sender_rejects_payload_hash_mismatch(tmp_path):
    envelope = _envelope()
    envelope["intent"] = "tampered after hash"

    result = send_wbs717_assignment(
        subject=build_assignment_subject(RUN_ID),
        envelope=envelope,
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=tmp_path / "sender.log",
        dry_run=True,
        now_at=NOW,
    )

    assert result.accepted is False
    assert "PAYLOAD_HASH_MISMATCH" in result.errors


def test_wbs717_sender_rejects_credential_values_and_endpoint_credentials():
    envelope = _envelope()

    credential = validate_sender_request(
        subject=build_assignment_subject(RUN_ID),
        envelope=envelope,
        credential_ref="nats://user:pass@192.168.31.124:4222",
        endpoint=ENDPOINT,
        now_at=NOW,
    )
    endpoint = validate_sender_request(
        subject=build_assignment_subject(RUN_ID),
        envelope=envelope,
        credential_ref=CREDENTIAL_REF,
        endpoint="nats://user:pass@192.168.31.124:4222",
        now_at=NOW,
    )

    assert credential.valid is False
    assert "CREDENTIAL_REF_MUST_NOT_BE_CREDENTIAL_VALUE" in credential.errors
    assert endpoint.valid is False
    assert "LIVE_ENDPOINT_MUST_NOT_EMBED_CREDENTIALS" in endpoint.errors
    assert endpoint_host_port_only("nats://user:pass@192.168.31.124:4222") == "invalid-endpoint-contains-credentials"


def test_wbs717_sender_accepts_file_path_credential_reference_without_logging_value(tmp_path):
    credential_ref = "/Users/alex/.openclaw/runtime/nats/nats-live-client.env"

    result = validate_sender_request(
        subject=build_assignment_subject(RUN_ID),
        envelope=_envelope(),
        credential_ref=credential_ref,
        endpoint=ENDPOINT,
        now_at=NOW,
    )

    assert result.valid is True


def test_wbs717_live_publisher_resolves_file_ref_in_memory_without_returning_value(tmp_path, monkeypatch):
    credential_file = tmp_path / "nats-live-client.env"
    credential_file.write_text("NATS_URL=nats://user:pass@192.168.31.124:4222\n", encoding="utf-8")
    captured = {}

    async def fake_publish(url, subject, payload, timeout_seconds):
        captured["url"] = url
        return PublishOutcome(accepted=True, publish_status="published")

    monkeypatch.setattr("nexus.mq.wbs717_nova_sender._publish_nats_core", fake_publish)

    outcome = LiveNatsAssignmentPublisher().publish(
        subject=build_assignment_subject(RUN_ID),
        payload=b"{}",
        credential_ref=str(credential_file),
        timeout_seconds=5,
    )

    assert outcome.accepted is True
    assert captured["url"] == "nats://user:pass@192.168.31.124:4222"
    assert "pass" not in str(outcome.to_dict()).lower()


def test_wbs717_evidence_package_writes_manifest_logs_and_secret_scan(tmp_path):
    envelope = _envelope()
    result = send_wbs717_assignment(
        subject=build_assignment_subject(RUN_ID),
        envelope=envelope,
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        audit_log_path=tmp_path / "logs" / "nova_assignment_sender.log",
        dry_run=True,
        duplicate_replay=True,
        now_at=NOW,
    )

    package = write_evidence_package(
        evidence_root=tmp_path,
        result=result,
        envelope=envelope,
        subject_manifest=build_subject_manifest(RUN_ID),
        credential_ref=CREDENTIAL_REF,
        endpoint=ENDPOINT,
        validation_failures=[{"case": "invalid_subject", "errors": ["WBS717_SUBJECT_NOT_RUN_SCOPED_ASSIGNMENT"]}],
    )

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "SHA256SUMS").exists()
    assert (tmp_path / "evidence" / "02_nova_sender_path_validation.json").exists()
    assert package["evidence_root"] == str(tmp_path)
    secret_scan = json.loads((tmp_path / "evidence" / "14_secret_scan.json").read_text(encoding="utf-8"))
    assert secret_scan["secret_values_found"] == 0
