from nexus.mq.live_transport_evidence import (
    contains_secret_material,
    evaluate_wbs717_evidence_gate,
    evidence_record,
)


def test_sender_only_evidence_cannot_pass_wbs717_gate():
    gate = evaluate_wbs717_evidence_gate(
        [
            evidence_record(
                "publish",
                message_id="msg-001",
                subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox",
                status="broker_received",
            )
        ]
    )

    assert gate.accepted is False
    assert "WBS717_SENDER_ONLY_EVIDENCE_CANNOT_PASS" in gate.errors
    assert "receive" in gate.missing_events
    assert gate.not_pass is True
    assert gate.not_business_completion is True


def test_secret_scan_rejects_secret_like_fields_and_values():
    assert contains_secret_material({"credential_ref": "credential-resolution://wbs717/stub"}) is False
    assert contains_secret_material({"api_key": "abc"}) is True
    assert contains_secret_material({"note": "Bearer abc"}) is True


def test_complete_transport_evidence_shape_is_gate_accepted_but_not_pass():
    records = [
        evidence_record("publish", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="broker_received"),
        evidence_record("receive", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="accepted"),
        evidence_record("ack", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="consumer_intake"),
        evidence_record("return", message_id="msg-result-001", subject="nexus.wbs7_17.wbs717-run-001.thunder.callbacks", status="broker_received"),
        evidence_record("duplicate", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="suppressed"),
        evidence_record("timeout_or_anomaly", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.ops.timeout", status="not_observed"),
        evidence_record("cleanup", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="not_started_runtime"),
        evidence_record("secret_scan", message_id="msg-001", subject="nexus.wbs7_17.wbs717-run-001.jarvis.inbox", status="clean"),
    ]

    gate = evaluate_wbs717_evidence_gate(records)

    assert gate.accepted is True
    assert gate.not_pass is True
    assert gate.not_business_completion is True
