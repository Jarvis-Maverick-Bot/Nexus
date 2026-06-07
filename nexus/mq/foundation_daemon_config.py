"""Source-only configuration gates for the Layer 3 MQ foundation daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

import yaml

from nexus.mq.agent_registry_events import secret_material_errors


FOUNDATION_DAEMON_SCHEMA_VERSION = "3.5.foundation-daemon.v1"
CONTROLLED_LIVE_ALLOWED_BROKER_URL = "nats://127.0.0.1:7422"
CONTROLLED_LIVE_BLOCKED_BROKER_URLS = {"nats://127.0.0.1:4222"}
CONTROLLED_LIVE_RUN_SCOPE = "3_5_wbs15_9_g6_20260607"
CONTROLLED_LIVE_SUBJECT_PREFIX = f"nexus.3_5.test.{CONTROLLED_LIVE_RUN_SCOPE}."
SOURCE_ONLY_ROLLOUT_PHASES = {"source_only", "dry_run", "disabled"}
ALLOWED_ROLLOUT_PHASES = SOURCE_ONLY_ROLLOUT_PHASES | {"controlled_live"}


@dataclass
class FoundationDaemonConfigValidation:
    valid: bool
    fail_closed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_hash: str = ""
    not_business_completion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "fail_closed": self.fail_closed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "config_hash": self.config_hash,
            "not_business_completion": self.not_business_completion,
        }


def load_foundation_daemon_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text) or {}
    elif config_path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError(f"UNSUPPORTED_CONFIG_FORMAT: {config_path.suffix}")
    if not isinstance(loaded, dict):
        raise ValueError("CONFIG_ROOT_MUST_BE_OBJECT")
    return loaded


def validate_foundation_daemon_config(config: dict[str, Any]) -> FoundationDaemonConfigValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(config, dict):
        errors.append("CONFIG_ROOT_MUST_BE_OBJECT")
        return _validation(errors, warnings, {})

    if config.get("manifest_version") != FOUNDATION_DAEMON_SCHEMA_VERSION:
        errors.append(f"UNSUPPORTED_MANIFEST_VERSION: {config.get('manifest_version')}")
    if config.get("environment") not in {"local", "staging", "source_only"}:
        errors.append(f"INVALID_ENVIRONMENT: {config.get('environment')}")

    daemon = _section(config, "daemon", errors)
    broker = _section(config, "broker", errors)
    subjects = _section(config, "subjects", errors)
    retry = _section(config, "retry", errors)
    timeout = _section(config, "timeout", errors)
    stores = _section(config, "stores", errors)
    feature_flags = _section(config, "feature_flags", errors)

    if daemon:
        _require(daemon, "runtime_instance_id", "daemon", errors)
        _require(daemon, "service_name", "daemon", errors)
        if daemon.get("default_enabled") is not False:
            errors.append("DEFAULT_ENABLED_NOT_ALLOWED_IN_SOURCE_PACKAGE")
        if daemon.get("rollout_phase") not in ALLOWED_ROLLOUT_PHASES:
            errors.append(f"INVALID_ROLLOUT_PHASE: {daemon.get('rollout_phase')}")

    if broker:
        _require_list(broker, "urls", "broker", errors)
        _require(broker, "stream", "broker", errors)
        _require(broker, "consumer", "broker", errors)
        _require(broker, "filter_subject", "broker", errors)
        _require(broker, "dlq_subject", "broker", errors)

    allowlist = []
    if subjects:
        allowlist = subjects.get("allowlist") or []
        if not isinstance(allowlist, list) or not allowlist:
            errors.append("MISSING_REQUIRED_FIELD: subjects.allowlist")
        elif broker:
            for field_name in ("filter_subject", "dlq_subject"):
                value = broker.get(field_name)
                if value and not subject_allowed(str(value), allowlist):
                    errors.append(f"SUBJECT_NOT_ALLOWED: broker.{field_name}")

    if retry:
        max_attempts = retry.get("max_attempts")
        if not isinstance(max_attempts, int) or max_attempts <= 0:
            errors.append("INVALID_RETRY_MAX_ATTEMPTS")
    if timeout:
        for field_name in ("endpoint_first_response_seconds", "endpoint_completion_seconds"):
            value = timeout.get(field_name)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"INVALID_TIMEOUT_SECONDS: {field_name}")

    if stores:
        _validate_store(stores, "durable_state", errors)
        _validate_store(stores, "evidence", errors)

    rollout_phase = daemon.get("rollout_phase") if daemon else None
    controlled_live = rollout_phase == "controlled_live"

    if feature_flags:
        if controlled_live:
            errors.extend(_controlled_live_authorization_errors(config, broker, subjects, stores, feature_flags))
        elif feature_flags.get("live_publish_enabled") is not False:
            errors.append("LIVE_PUBLISH_NOT_AUTHORIZED_FOR_SOURCE_GATE")
        if feature_flags.get("business_dispatch_enabled") is not False:
            errors.append("BUSINESS_DISPATCH_OUT_OF_SCOPE")
        if feature_flags.get("broker_setup_enabled") is not False:
            errors.append("BROKER_SETUP_MUTATION_OUT_OF_SCOPE")
        if feature_flags.get("private_agent_invocation_enabled") is True:
            errors.append("PRIVATE_AGENT_INVOCATION_OUT_OF_SCOPE")

    errors.extend(secret_material_errors(config, path="config"))
    return _validation(errors, warnings, config)


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(config, sort_keys=True))
    broker = redacted.get("broker")
    if isinstance(broker, dict):
        broker["urls"] = [_redact_url(str(url)) for url in broker.get("urls", [])]
    stores = redacted.get("stores")
    if isinstance(stores, dict):
        for store in stores.values():
            if isinstance(store, dict) and "dsn" in store:
                store["dsn"] = _redact_url(str(store["dsn"]))
    secret_refs = redacted.get("secret_refs")
    if isinstance(secret_refs, dict):
        redacted["secret_refs"] = {key: "ref-present" if value else "" for key, value in secret_refs.items()}
    return redacted


def config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(redact_config(config), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def subject_allowed(subject: str, allowlist: list[str]) -> bool:
    return any(_subject_pattern_matches(subject, str(pattern)) for pattern in allowlist)


def is_controlled_live_requested(config: dict[str, Any]) -> bool:
    daemon = config.get("daemon", {}) if isinstance(config, dict) else {}
    return daemon.get("rollout_phase") == "controlled_live"


def is_controlled_live_authorized(config: dict[str, Any]) -> bool:
    return is_controlled_live_requested(config) and validate_foundation_daemon_config(config).valid


def _subject_pattern_matches(subject: str, pattern: str) -> bool:
    subject_parts = subject.split(".")
    pattern_parts = pattern.split(".")
    for index, pattern_part in enumerate(pattern_parts):
        if pattern_part == ">":
            return index == len(pattern_parts) - 1 and len(subject_parts) >= index
        if index >= len(subject_parts):
            return False
        if pattern_part != "*" and pattern_part != subject_parts[index]:
            return False
    return len(subject_parts) == len(pattern_parts)


def _validation(
    errors: list[str],
    warnings: list[str],
    config: dict[str, Any],
) -> FoundationDaemonConfigValidation:
    return FoundationDaemonConfigValidation(
        valid=not errors,
        fail_closed=bool(errors),
        errors=list(dict.fromkeys(errors)),
        warnings=warnings,
        config_hash=config_hash(config) if isinstance(config, dict) else "",
    )


def _section(config: dict[str, Any], name: str, errors: list[str]) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        errors.append(f"MISSING_REQUIRED_SECTION: {name}")
        return {}
    return value


def _require(section: dict[str, Any], field_name: str, section_name: str, errors: list[str]) -> None:
    if section.get(field_name) in (None, ""):
        errors.append(f"MISSING_REQUIRED_FIELD: {section_name}.{field_name}")


def _require_list(section: dict[str, Any], field_name: str, section_name: str, errors: list[str]) -> None:
    value = section.get(field_name)
    if not isinstance(value, list) or not value:
        errors.append(f"MISSING_REQUIRED_FIELD: {section_name}.{field_name}")


def _validate_store(stores: dict[str, Any], name: str, errors: list[str]) -> None:
    store = stores.get(name)
    if not isinstance(store, dict):
        errors.append(f"MISSING_REQUIRED_SECTION: stores.{name}")
        return
    _require(store, "dsn", f"stores.{name}", errors)
    _require_list(store, "required_families", f"stores.{name}", errors)


def _controlled_live_authorization_errors(
    config: dict[str, Any],
    broker: dict[str, Any],
    subjects: dict[str, Any],
    stores: dict[str, Any],
    feature_flags: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    controlled_live = config.get("controlled_live")
    if not isinstance(controlled_live, dict):
        errors.append("MISSING_REQUIRED_SECTION: controlled_live")
        return errors

    for field_name in ("run_id", "run_packet_ref", "authorization_ref", "route_scope"):
        if controlled_live.get(field_name) in (None, ""):
            errors.append(f"MISSING_REQUIRED_FIELD: controlled_live.{field_name}")

    if controlled_live.get("run_id") != CONTROLLED_LIVE_RUN_SCOPE:
        errors.append("CONTROLLED_LIVE_RUN_SCOPE_NOT_AUTHORIZED")
    if controlled_live.get("route_scope") != "nexus_local_test_only":
        errors.append("CONTROLLED_LIVE_ROUTE_SCOPE_NOT_AUTHORIZED")

    if feature_flags.get("live_publish_enabled") is not True:
        errors.append("CONTROLLED_LIVE_REQUIRES_LIVE_PUBLISH_ENABLED")

    urls = broker.get("urls") if isinstance(broker, dict) else None
    if not isinstance(urls, list) or urls != [CONTROLLED_LIVE_ALLOWED_BROKER_URL]:
        errors.append("CONTROLLED_LIVE_ROUTE_NOT_AUTHORIZED")
    elif any(str(url) in CONTROLLED_LIVE_BLOCKED_BROKER_URLS for url in urls):
        errors.append("CONTROLLED_LIVE_ROUTE_NOT_AUTHORIZED")

    scoped_broker_values = [
        broker.get("stream"),
        broker.get("consumer"),
        broker.get("filter_subject"),
        broker.get("dlq_subject"),
    ]
    if not all(_contains_run_scope(value) for value in scoped_broker_values):
        errors.append("CONTROLLED_LIVE_BROKER_SCOPE_NOT_RUN_SCOPED")

    allowlist = subjects.get("allowlist") if isinstance(subjects, dict) else None
    if not isinstance(allowlist, list) or not allowlist:
        errors.append("CONTROLLED_LIVE_SUBJECT_SCOPE_NOT_TEST_SCOPED")
    else:
        for subject in allowlist:
            value = str(subject)
            if "*" in value or ">" in value or not value.startswith(CONTROLLED_LIVE_SUBJECT_PREFIX):
                errors.append("CONTROLLED_LIVE_SUBJECT_SCOPE_NOT_TEST_SCOPED")
                break
        for field_name in ("filter_subject", "dlq_subject"):
            value = str(broker.get(field_name, ""))
            if not value.startswith(CONTROLLED_LIVE_SUBJECT_PREFIX):
                errors.append("CONTROLLED_LIVE_SUBJECT_SCOPE_NOT_TEST_SCOPED")
                break

    for store_name in ("durable_state", "evidence"):
        store = stores.get(store_name) if isinstance(stores, dict) else None
        dsn = store.get("dsn") if isinstance(store, dict) else ""
        if CONTROLLED_LIVE_RUN_SCOPE not in str(dsn):
            errors.append(f"CONTROLLED_LIVE_STORE_NOT_RUN_SCOPED: stores.{store_name}")

    return errors


def _contains_run_scope(value: Any) -> bool:
    return CONTROLLED_LIVE_RUN_SCOPE.lower() in str(value or "").lower()


def _redact_url(value: str) -> str:
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    host = rest.split("@", 1)[1]
    return f"{scheme}://***@{host}"
