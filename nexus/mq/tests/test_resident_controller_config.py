from nexus.mq.resident_controller.config import (
    build_redacted_config_snapshot,
    validate_resident_controller_config,
)


def _config(**overrides):
    data = {
        "schema_version": "resident_controller.v0.2",
        "controller": {
            "controller_id": "resident-controller-nova-mac",
            "runtime_instance_id": "resident-controller-run-001",
            "environment": "bounded_uat",
            "launch_mode": "disabled",
            "run_authorization_ref": "review-evidence/nova/uat-auth.md",
            "allowed_wbs_ids": ["7.19.14.5"],
        },
        "broker": {
            "nats_url_ref": "env:NEXUS_RESIDENT_CONTROLLER_NATS_URL",
            "auth_ref": "env:NEXUS_RESIDENT_CONTROLLER_NATS_AUTH_REF",
            "connect_timeout_seconds": 10,
            "subscription_ready_timeout_seconds": 10,
        },
        "subjects": {
            "namespace": "nexus.4_19.wbs7_19_14",
            "subscribe_allowlist": ["nexus.4_19.wbs7_19_14.*.heartbeat.>"],
            "publish_allowlist": ["nexus.4_19.wbs7_19_14.*.controller.init"],
        },
        "runtimes": {
            "allowed_agents": ["jarvis"],
            "required_capabilities": ["controlled_uat_handoff_receive"],
            "heartbeat_ttl_seconds": 30,
            "stale_after_missed_heartbeats": 2,
        },
        "policy": {
            "production_business_execution_allowed": False,
            "private_agent_invocation_allowed": False,
            "broker_mutation_allowed": False,
            "autonomous_acceptance_allowed": False,
            "require_non_loopback_for_distributed_uat": True,
            "command_allowlist": ["controller_init", "bounded_assignment", "duplicate_replay", "drain"],
        },
        "evidence": {
            "root": "evidence/4.19/wbs-7.19.14/resident-controller/run-001",
            "raw_log": "events.jsonl",
            "manifest": "manifest.json",
            "summary": "verdict_report.md",
            "secret_scan_required": True,
        },
        "recovery": {
            "checkpoint_file": "controller_state.json",
            "reconnect_max_attempts": 3,
            "reconnect_backoff_seconds": [1, 2, 5],
            "assignment_ack_timeout_seconds": 30,
            "result_candidate_timeout_seconds": 120,
        },
    }
    data.update(overrides)
    return data


def test_resident_controller_config_requires_authorization_ref():
    config = _config(
        controller={
            "controller_id": "resident-controller-nova-mac",
            "runtime_instance_id": "resident-controller-run-001",
            "environment": "bounded_uat",
            "launch_mode": "disabled",
            "run_authorization_ref": "",
            "allowed_wbs_ids": ["7.19.14.5"],
        }
    )

    result = validate_resident_controller_config(config)

    assert result.valid is False
    assert result.fail_closed is True
    assert "MISSING_RUN_AUTHORIZATION_REF" in result.errors
    assert result.live_runtime_allowed is False


def test_resident_controller_config_rejects_secret_values_and_redacts_output():
    config = _config(
        broker={
            "nats_url_ref": "nats://user:pass@127.0.0.1:4222",
            "auth_ref": "token=" + "abc123",
            "connect_timeout_seconds": 10,
            "subscription_ready_timeout_seconds": 10,
        }
    )

    result = validate_resident_controller_config(config)
    snapshot = build_redacted_config_snapshot(config)

    assert result.valid is False
    assert any(error.startswith("SECRET_MATERIAL_VALUE") for error in result.errors)
    assert snapshot["broker"]["nats_url_ref"] == "redacted-ref-present"
    assert snapshot["broker"]["auth_ref"] == "redacted-ref-present"
    assert "abc123" not in str(snapshot)


def test_resident_controller_config_rejects_unsafe_policy_flags():
    config = _config(
        policy={
            "production_business_execution_allowed": True,
            "private_agent_invocation_allowed": True,
            "broker_mutation_allowed": True,
            "autonomous_acceptance_allowed": True,
            "require_non_loopback_for_distributed_uat": True,
            "command_allowlist": ["controller_init"],
        }
    )

    result = validate_resident_controller_config(config)

    assert result.valid is False
    assert "PRODUCTION_BUSINESS_EXECUTION_NOT_AUTHORIZED" in result.errors
    assert "PRIVATE_AGENT_INVOCATION_NOT_AUTHORIZED" in result.errors
    assert "BROKER_MUTATION_NOT_AUTHORIZED" in result.errors
    assert "AUTONOMOUS_ACCEPTANCE_NOT_AUTHORIZED" in result.errors
