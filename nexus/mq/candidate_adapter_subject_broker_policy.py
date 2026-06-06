"""Candidate Adapter broker and subject policy checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
CANONICAL_ASSIGNMENT_NAMESPACE = "nexus.4_19.wbs7_19_15"
LEGACY_ASSIGNMENT_NAMESPACES = ("nexus.4_19.wbs7_19_14",)
ALLOWED_ASSIGNMENT_NAMESPACES = (CANONICAL_ASSIGNMENT_NAMESPACE, *LEGACY_ASSIGNMENT_NAMESPACES)
CANONICAL_ASSIGNMENT_AGENT_ID = "jarvis"
ADDITIONAL_ASSIGNMENT_AGENT_IDS = ("thunder_codex_app",)
ALLOWED_ASSIGNMENT_AGENT_IDS = (CANONICAL_ASSIGNMENT_AGENT_ID, *ADDITIONAL_ASSIGNMENT_AGENT_IDS)


@dataclass
class CandidateAdapterPolicyDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    not_business_completion: bool = True


def validate_broker_endpoint(
    broker_url: str,
    *,
    local_only_authorization: bool = False,
) -> CandidateAdapterPolicyDecision:
    errors: list[str] = []
    if not broker_url:
        return CandidateAdapterPolicyDecision(False, ["MISSING_BROKER_URL"])

    parsed = urlparse(broker_url)
    if parsed.scheme != "nats":
        errors.append(f"UNSUPPORTED_BROKER_SCHEME: {parsed.scheme or '<missing>'}")
    if not parsed.hostname:
        errors.append("MISSING_BROKER_HOST")
    if parsed.username or parsed.password:
        errors.append("BROKER_URL_MUST_NOT_EMBED_CREDENTIALS")

    host = parsed.hostname or ""
    port = parsed.port
    if not local_only_authorization:
        if host.lower() in LOOPBACK_HOSTS:
            errors.append(f"BROKER_LOOPBACK_FORBIDDEN_FOR_DISTRIBUTED_UAT: {host}")
        if port == 4222:
            errors.append(f"BROKER_ENDPOINT_FORBIDDEN_FOR_DISTRIBUTED_UAT: {host}:{port}")
    return CandidateAdapterPolicyDecision(not errors, _dedupe(errors))


def validate_subject_patterns(patterns: list[str]) -> CandidateAdapterPolicyDecision:
    errors: list[str] = []
    if not patterns:
        return CandidateAdapterPolicyDecision(False, ["MISSING_ALLOWED_SUBJECT_PATTERNS"])
    for pattern in patterns:
        if not pattern:
            errors.append("EMPTY_SUBJECT_PATTERN")
            continue
        if _is_broad_subject_pattern(pattern):
            errors.append(f"UNAUTHORIZED_SUBJECT_PATTERN: {pattern}")
    return CandidateAdapterPolicyDecision(not errors, _dedupe(errors))


def validate_assignment_subject(subject: str, patterns: list[str]) -> CandidateAdapterPolicyDecision:
    pattern_decision = validate_subject_patterns(patterns)
    errors = list(pattern_decision.errors)
    if not subject:
        errors.append("MISSING_ASSIGNMENT_SUBJECT")
    else:
        errors.extend(_canonical_assignment_subject_errors(subject))
        if not any(subject_matches_pattern(subject, pattern) for pattern in patterns):
            errors.append(f"ASSIGNMENT_SUBJECT_NOT_ALLOWED: {subject}")
    return CandidateAdapterPolicyDecision(not errors, _dedupe(errors))


def subject_matches_pattern(subject: str, pattern: str) -> bool:
    subject_tokens = subject.split(".")
    pattern_tokens = pattern.split(".")
    for index, token in enumerate(pattern_tokens):
        if token == ">":
            return index < len(pattern_tokens) and index <= len(subject_tokens)
        if index >= len(subject_tokens):
            return False
        if token != "*" and token != subject_tokens[index]:
            return False
    return len(subject_tokens) == len(pattern_tokens)


def _is_broad_subject_pattern(pattern: str) -> bool:
    stripped = pattern.strip()
    if stripped in {"*", ">", "*.*", "*.*.*"}:
        return True
    tokens = stripped.split(".")
    if tokens[0] in {"*", ">"}:
        return True
    if stripped in {"nexus.>", "nexus.*", "nats.>"}:
        return True
    return False


def _canonical_assignment_subject_errors(subject: str) -> list[str]:
    parts = subject.split(".")
    if _is_runtime_scoped_assignment_alias(parts):
        return ["ASSIGNMENT_SUBJECT_RUNTIME_ALIAS_DIAGNOSTIC_ONLY"]

    namespace_parts = _matching_namespace_parts(parts)
    if namespace_parts is None:
        return [f"ASSIGNMENT_SUBJECT_NOT_CANONICAL: {subject}"]
    if _is_canonical_duplicate_replay_subject(parts, namespace_parts):
        return []
    if len(parts) != len(namespace_parts) + 3:
        return [f"ASSIGNMENT_SUBJECT_NOT_CANONICAL: {subject}"]
    if not parts[len(namespace_parts)]:
        return [f"ASSIGNMENT_SUBJECT_NOT_CANONICAL: {subject}"]
    if parts[len(namespace_parts) + 1] not in ALLOWED_ASSIGNMENT_AGENT_IDS:
        return [f"ASSIGNMENT_SUBJECT_NOT_CANONICAL: {subject}"]
    if parts[-1] != "assignment":
        return [f"ASSIGNMENT_SUBJECT_NOT_CANONICAL: {subject}"]
    return []


def _is_canonical_duplicate_replay_subject(parts: list[str], namespace_parts: list[str]) -> bool:
    return (
        len(parts) == len(namespace_parts) + 4
        and bool(parts[len(namespace_parts)])
        and parts[len(namespace_parts) + 1] in ALLOWED_ASSIGNMENT_AGENT_IDS
        and parts[-2:] == ["assignment", "duplicate_replay"]
    )


def _is_runtime_scoped_assignment_alias(parts: list[str]) -> bool:
    namespace_parts = _matching_namespace_parts(parts)
    if namespace_parts is None:
        return False
    return (
        len(parts) == len(namespace_parts) + 4
        and bool(parts[len(namespace_parts)])
        and parts[len(namespace_parts) + 1] in ALLOWED_ASSIGNMENT_AGENT_IDS
        and bool(parts[len(namespace_parts) + 2])
        and parts[-1] == "assignment"
    )


def _matching_namespace_parts(parts: list[str]) -> list[str] | None:
    for namespace in ALLOWED_ASSIGNMENT_NAMESPACES:
        namespace_parts = namespace.split(".")
        if parts[: len(namespace_parts)] == namespace_parts:
            return namespace_parts
    return None


def _dedupe(errors: list[str]) -> list[str]:
    deduped: list[str] = []
    for error in errors:
        if error not in deduped:
            deduped.append(error)
    return deduped
