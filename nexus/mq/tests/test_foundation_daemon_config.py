import json
import subprocess
import sys

from nexus.mq.foundation_daemon_config import (
    config_hash,
    load_foundation_daemon_config,
    redact_config,
    subject_allowed,
    validate_foundation_daemon_config,
)


def _config(**overrides):
    data = {
        "manifest_version": "3.5.foundation-daemon.v1",
        "environment": "local",
        "daemon": {
            "runtime_instance_id": "layer3-foundation-daemon-local",
            "service_name": "nexus-mq-foundation-daemon",
            "default_enabled": False,
            "rollout_phase": "source_only",
            "lifecycle_timeouts": {"start_seconds": 10, "stop_seconds": 10, "drain_seconds": 10},
        },
        "broker": {
            "urls": ["nats://127.0.0.1:4222"],
            "stream": "NEXUS_MQ_FOUNDATION",
            "consumer": "nexus-mq-foundation-daemon",
            "filter_subject": "nexus.3_5.mq.inbox",
            "dlq_subject": "nexus.3_5.mq.dlq",
        },
        "subjects": {
            "allowlist": [
                "nexus.3_5.mq.inbox",
                "nexus.3_5.mq.results",
                "nexus.3_5.mq.retry",
                "nexus.3_5.mq.timeout",
                "nexus.3_5.mq.dlq",
            ]
        },
        "retry": {"max_attempts": 3, "backoff_seconds": [0, 0, 0]},
        "timeout": {"endpoint_first_response_seconds": 30, "endpoint_completion_seconds": 120},
        "stores": {
            "durable_state": {
                "dsn": "sqlite:///tmp/nexus-mq-foundation-daemon-state.sqlite3",
                "required_families": ["foundation_intake", "foundation_dlq"],
            },
            "evidence": {
                "dsn": "file://tmp/nexus-mq-foundation-daemon-evidence",
                "required_families": ["status", "intake", "retry", "dlq"],
            },
        },
        "secret_refs": {"nats_credentials_ref": "secret-ref://local/nats"},
        "feature_flags": {
            "live_publish_enabled": False,
            "business_dispatch_enabled": False,
            "broker_setup_enabled": False,
        },
    }
    for key, value in overrides.items():
        data[key] = value
    return data


def test_foundation_daemon_config_accepts_default_off_source_config():
    result = validate_foundation_daemon_config(_config())

    assert result.valid is True
    assert result.fail_closed is False
    assert result.not_business_completion is True


def test_foundation_daemon_config_rejects_default_enabled_and_live_flags():
    data = _config()
    data["daemon"]["default_enabled"] = True
    data["feature_flags"]["live_publish_enabled"] = True
    data["feature_flags"]["business_dispatch_enabled"] = True
    data["feature_flags"]["broker_setup_enabled"] = True

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert "DEFAULT_ENABLED_NOT_ALLOWED_IN_SOURCE_PACKAGE" in result.errors
    assert "LIVE_PUBLISH_NOT_AUTHORIZED_FOR_SOURCE_GATE" in result.errors
    assert "BUSINESS_DISPATCH_OUT_OF_SCOPE" in result.errors
    assert "BROKER_SETUP_MUTATION_OUT_OF_SCOPE" in result.errors


def test_foundation_daemon_config_rejects_secret_material_recursively():
    data = _config()
    data["broker"]["api_key"] = "not-allowed"
    data["stores"]["durable_state"]["dsn"] = "sqlite:///tmp/db?token=abc"
    data["nested"] = {"value": "sk-test-secret-like"}

    result = validate_foundation_daemon_config(data)

    assert result.valid is False
    assert any(error.startswith("SECRET_MATERIAL_FIELD: config.broker.api_key") for error in result.errors)
    assert any(error.startswith("SECRET_MATERIAL_VALUE: config.stores.durable_state.dsn") for error in result.errors)
    assert any(error.startswith("SECRET_MATERIAL_VALUE: config.nested.value") for error in result.errors)


def test_foundation_daemon_config_hash_is_deterministic_after_redaction():
    first = config_hash(_config())
    second = config_hash(_config())

    assert first == second
    assert first.startswith("sha256:")
    assert "redacted_at" not in redact_config(_config())


def test_foundation_daemon_subject_policy_rejects_extra_segments():
    allowed = _config()["subjects"]["allowlist"]

    assert subject_allowed("nexus.3_5.mq.inbox", allowed) is True
    assert subject_allowed("nexus.3_5.mq.inbox.extra", allowed) is False


def test_foundation_daemon_cli_validate_config_reads_committed_yaml():
    command = [
        sys.executable,
        "-m",
        "nexus.mq.foundation_daemon",
        "validate-config",
        "--config",
        "config/mq/foundation_daemon.example.yaml",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["valid"] is True
    assert payload["not_business_completion"] is True


def test_foundation_daemon_load_config_supports_yaml(tmp_path):
    path = tmp_path / "foundation.yaml"
    path.write_text(
        "manifest_version: 3.5.foundation-daemon.v1\n"
        "environment: local\n"
        "daemon:\n"
        "  runtime_instance_id: layer3-foundation-daemon-local\n"
        "  service_name: nexus-mq-foundation-daemon\n"
        "  default_enabled: false\n"
        "  rollout_phase: source_only\n",
        encoding="utf-8",
    )

    loaded = load_foundation_daemon_config(path)

    assert loaded["daemon"]["default_enabled"] is False
