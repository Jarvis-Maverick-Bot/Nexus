import json
from hashlib import sha256

from nexus.mq.controller_bridge_cli import main
from nexus.mq.controller_bridge_models import ControllerBridgePolicy, policy_hash
from nexus.mq.controller_bridge_state_store import ControllerBridgeStateStore
from nexus.mq.durable_state import DurableStateStore


NOW = "2026-05-27T12:00:00+00:00"
CANONICAL_ASSIGNMENT_SUBJECT = "nexus.4_19.wbs7_19_14.run-001.jarvis.assignment"
RUNTIME_SCOPED_ASSIGNMENT_ALIAS = "nexus.4_19.wbs7_19_14.run-001.jarvis.jarvis-runtime-001.assignment"


def _write_json(path, payload):
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _decision_payload():
    return {
        "decision_id": "decision-001",
        "decision_authority_ref": "review://nova/controller-bridge",
        "owner_principal_id": "principal://alex",
        "work_class": "non_business_probe",
        "source_refs": {"shared_docs_commit": "c3ef7b3"},
        "dispatch_packet_ref": "dispatch-packet://controller-bridge/run-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "target_runtime_role": "implementation_agent",
        "allowed_runtime_roles": ["implementation_agent"],
        "required_capability": "implementation",
        "required_authority_scope": "workflow.command",
        "required_privacy_scope": "project",
        "allowed_task_boundary": "implementation",
        "required_protocol_version": "4.19.candidate_adapter.v1",
        "no_go_scope": ["no business execution"],
        "evidence_required": ["dispatch", "lifecycle", "lease"],
        "idempotency_key": "idem-001",
        "expires_at": "2026-05-27T12:10:00+00:00",
    }


def _runtime_decision_payload():
    return {
        "decision_id": "runtime-decision-001",
        "request_id": f"eligibility-{sha256('run-001|assignment-001|idem-001'.encode('utf-8')).hexdigest()[:12]}",
        "dispatch_run_id": "run-001",
        "assignment_id": "assignment-001",
        "target_agent_id": "jarvis",
        "target_runtime_instance_id": "jarvis-runtime-001",
        "accepted": True,
        "policy_hash": policy_hash(ControllerBridgePolicy()),
        "idempotency_key": "idem-001",
        "valid_until": "2026-05-27T12:00:30+00:00",
        "runtime_role": "implementation_agent",
        "runtime_owner": "principal://jarvis",
    }


def test_controller_bridge_cli_dispatch_validate_create_publish(tmp_path, capsys):
    state_db = tmp_path / "bridge.sqlite3"
    decision_json = _write_json(tmp_path / "decision.json", _decision_payload())
    runtime_decision_json = _write_json(tmp_path / "runtime-decision.json", _runtime_decision_payload())

    assert main(["dispatch", "validate", "--decision-json", str(decision_json), "--now-at", NOW]) == 0
    validate_output = json.loads(capsys.readouterr().out)
    assert validate_output["accepted"] is True

    assert (
        main(
            [
                "dispatch",
                "create",
                "--state-db",
                str(state_db),
                "--decision-json",
                str(decision_json),
                "--run-id",
                "run-001",
                "--assignment-id",
                "assignment-001",
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    create_output = json.loads(capsys.readouterr().out)
    assert create_output["accepted"] is True

    assert main(["runtime", "eligibility", "--state-db", str(state_db), "--decision-json", str(runtime_decision_json)]) == 0
    eligibility_output = json.loads(capsys.readouterr().out)
    assert eligibility_output["accepted"] is True

    assert (
        main(
            [
                "runtime",
                "reserve",
                "--state-db",
                str(state_db),
                "--decision-id",
                "runtime-decision-001",
                "--lease-id",
                "lease-001",
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    reserve_output = json.loads(capsys.readouterr().out)
    assert reserve_output["payload"]["lease"]["lease_id"] == "lease-001"

    assert (
        main(
            [
                "dispatch",
                "publish-assignment",
                "--state-db",
                str(state_db),
                "--run-id",
                "run-001",
                "--assignment-id",
                "assignment-001",
                "--decision-id",
                "runtime-decision-001",
                "--lease-id",
                "lease-001",
                "--runtime-instance-id",
                "jarvis-runtime-001",
                "--idempotency-key",
                "idem-001",
                "--subject",
                CANONICAL_ASSIGNMENT_SUBJECT,
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    publish_output = json.loads(capsys.readouterr().out)
    assert publish_output["accepted"] is True
    assert publish_output["payload"]["assignment_publish_request"]["reservation_lease_id"] == "lease-001"


def test_controller_bridge_cli_dispatch_publish_rejects_runtime_scoped_assignment_alias(tmp_path, capsys):
    state_db = tmp_path / "bridge.sqlite3"
    decision_json = _write_json(tmp_path / "decision.json", _decision_payload())
    runtime_decision_json = _write_json(tmp_path / "runtime-decision.json", _runtime_decision_payload())

    assert main(["dispatch", "create", "--state-db", str(state_db), "--decision-json", str(decision_json), "--run-id", "run-001", "--assignment-id", "assignment-001", "--now-at", NOW]) == 0
    capsys.readouterr()
    assert main(["runtime", "eligibility", "--state-db", str(state_db), "--decision-json", str(runtime_decision_json)]) == 0
    capsys.readouterr()
    assert main(["runtime", "reserve", "--state-db", str(state_db), "--decision-id", "runtime-decision-001", "--lease-id", "lease-001", "--now-at", NOW]) == 0
    capsys.readouterr()

    code = main(
        [
            "dispatch",
            "publish-assignment",
            "--state-db",
            str(state_db),
            "--run-id",
            "run-001",
            "--assignment-id",
            "assignment-001",
            "--decision-id",
            "runtime-decision-001",
            "--lease-id",
            "lease-001",
            "--runtime-instance-id",
            "jarvis-runtime-001",
            "--idempotency-key",
            "idem-001",
            "--subject",
            RUNTIME_SCOPED_ASSIGNMENT_ALIAS,
            "--now-at",
            NOW,
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert code == 1
    assert output["accepted"] is False
    assert "PUBLISH_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY" in output["errors"]


def test_controller_bridge_cli_dispatch_request_eligibility_persists_lifecycle_decision_without_runtime_mutation(
    tmp_path, capsys
):
    state_db = tmp_path / "bridge.sqlite3"
    decision_json = _write_json(tmp_path / "decision.json", _decision_payload())
    runtime_decision_json = _write_json(tmp_path / "runtime-decision.json", _runtime_decision_payload())

    assert (
        main(
            [
                "dispatch",
                "create",
                "--state-db",
                str(state_db),
                "--decision-json",
                str(decision_json),
                "--run-id",
                "run-001",
                "--assignment-id",
                "assignment-001",
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "dispatch",
                "request-eligibility",
                "--state-db",
                str(state_db),
                "--run-id",
                "run-001",
                "--lifecycle-decision-json",
                str(runtime_decision_json),
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    store = ControllerBridgeStateStore(DurableStateStore(str(state_db)))

    assert output["accepted"] is True
    assert output["operation"] == "request_eligibility"
    assert output["payload"]["lifecycle_decision"]["decision_id"] == "runtime-decision-001"
    assert output["payload"]["runtime_lifecycle_provider"]["mutating_calls"] == []
    assert store.get_lifecycle_decision("runtime-decision-001").accepted is True
    store.close()


def test_controller_bridge_cli_runtime_lease_status_and_release(tmp_path, capsys):
    state_db = tmp_path / "bridge.sqlite3"
    runtime_decision_json = _write_json(tmp_path / "runtime-decision.json", _runtime_decision_payload())

    assert main(["runtime", "eligibility", "--state-db", str(state_db), "--decision-json", str(runtime_decision_json)]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "runtime",
                "reserve",
                "--state-db",
                str(state_db),
                "--decision-id",
                "runtime-decision-001",
                "--lease-id",
                "lease-001",
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["runtime", "lease-status", "--state-db", str(state_db), "--lease-id", "lease-001", "--now-at", NOW]) == 0
    status_output = json.loads(capsys.readouterr().out)
    assert status_output["payload"]["lease"]["status"] == "active"

    assert (
        main(
            [
                "runtime",
                "release",
                "--state-db",
                str(state_db),
                "--lease-id",
                "lease-001",
                "--reason-ref",
                "drain://run-001",
                "--now-at",
                NOW,
            ]
        )
        == 0
    )
    release_output = json.loads(capsys.readouterr().out)
    assert release_output["payload"]["lease"]["status"] == "released"
