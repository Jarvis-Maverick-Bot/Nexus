"""Bounded foreground resident-controller start-once runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
import asyncio
import json
import threading
import time

from nexus.mq.eligibility_reservation_policy import RuntimeEligibilityDecision, RuntimeReservationLease
from nexus.mq.resident_controller.config import validate_resident_controller_config
from nexus.mq.resident_controller.dispatcher import (
    DEFAULT_ALLOWED_WBS_IDS,
    ResidentControllerDispatchPolicy,
    ResidentControllerDispatchRequest,
    ResidentControllerSubjectPolicy,
    evaluate_resident_dispatch,
    validate_publish_subject,
)
from nexus.mq.resident_controller.evidence import EvidencePackageResult, ResidentEvidenceRecord, build_evidence_package
from nexus.mq.resident_controller.service import build_status_snapshot

try:
    import nats

    HAS_NATS = True
except ImportError:  # pragma: no cover - covered by runtime posture evidence when dependency is absent
    nats = None
    HAS_NATS = False


MessageHandler = Callable[[str, dict[str, Any]], None]
MIN_POST_ASSIGNMENT_OBSERVATION_SECONDS = 90.0
DEFAULT_DUPLICATE_REPLAY_SUPPRESSION_TIMEOUT_SECONDS = 30.0


class ResidentBrokerClient(Protocol):
    def connect(self, *, nats_url: str, auth_ref: str, connect_timeout_seconds: int) -> None:
        ...

    def subscribe(self, subject: str, handler: MessageHandler) -> None:
        ...

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        ...

    def drain(self) -> None:
        ...

    def close(self) -> None:
        ...


class ResidentLifecycleProvider(Protocol):
    def assignment_decision_and_lease(
        self,
        *,
        run_id: str,
        agent_id: str,
        assignment_id: str,
        idempotency_key: str,
        target_runtime_instance_id: str,
        now_at: str,
    ) -> tuple[RuntimeEligibilityDecision | None, RuntimeReservationLease | None]:
        ...


class MissingResidentLifecycleProvider:
    def assignment_decision_and_lease(
        self,
        *,
        run_id: str,
        agent_id: str,
        assignment_id: str,
        idempotency_key: str,
        target_runtime_instance_id: str,
        now_at: str,
    ) -> tuple[RuntimeEligibilityDecision | None, RuntimeReservationLease | None]:
        return None, None


class BoundedUatResidentLifecycleProvider:
    """Builds bounded non-production lifecycle evidence for start-once UAT dispatch."""

    def assignment_decision_and_lease(
        self,
        *,
        run_id: str,
        agent_id: str,
        assignment_id: str,
        idempotency_key: str,
        target_runtime_instance_id: str,
        now_at: str,
    ) -> tuple[RuntimeEligibilityDecision | None, RuntimeReservationLease | None]:
        suffix = sha256(
            f"{run_id}|{agent_id}|{assignment_id}|{idempotency_key}|{target_runtime_instance_id}".encode("utf-8")
        ).hexdigest()[:12]
        expires_at = _iso_after(now_at, seconds=3600)
        policy_hash = f"bounded-uat-{suffix}"
        decision = RuntimeEligibilityDecision(
            decision_id=f"decision-{run_id}-{assignment_id}-{suffix}",
            request_id=f"eligibility-{run_id}-{assignment_id}-{suffix}",
            dispatch_run_id=run_id,
            assignment_id=assignment_id,
            target_agent_id=agent_id,
            target_runtime_instance_id=target_runtime_instance_id,
            accepted=True,
            policy_hash=policy_hash,
            idempotency_key=idempotency_key,
            valid_until=expires_at,
            runtime_role="bounded_uat_candidate",
            runtime_owner=agent_id,
            evidence_refs=[f"evidence://resident-controller/{run_id}/bounded-uat-lifecycle/{assignment_id}"],
            not_business_completion=True,
        )
        lease = RuntimeReservationLease(
            lease_id=f"lease-{run_id}-{assignment_id}-{suffix}",
            lifecycle_decision_id=decision.decision_id,
            assignment_id=assignment_id,
            dispatch_run_id=run_id,
            target_runtime_instance_id=target_runtime_instance_id,
            active=True,
            status="active",
            expires_at=expires_at,
            policy_hash=policy_hash,
            idempotency_key=idempotency_key,
            release_required_by=expires_at,
            runtime_role="bounded_uat_candidate",
            runtime_owner=agent_id,
            not_business_completion=True,
        )
        return decision, lease


@dataclass
class ResidentStartOnceRuntimeResult:
    accepted: bool
    daemon_started: bool
    service_state: str
    errors: list[str] = field(default_factory=list)
    evidence_records: list[ResidentEvidenceRecord] = field(default_factory=list)
    status_snapshot: dict[str, Any] = field(default_factory=dict)
    evidence_package: EvidencePackageResult | None = None
    not_business_completion: bool = True


@dataclass
class PublishedAssignment:
    agent_id: str
    subject: str
    payload: dict[str, Any]
    published_at: str


class NatsResidentBrokerClient:
    """Small NATS core client for resident-controller UAT subjects."""

    def __init__(self) -> None:
        if not HAS_NATS:
            raise RuntimeError("NATS_PY_NOT_INSTALLED")
        self._nc = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._loop_ready: threading.Event | None = None

    def connect(self, *, nats_url: str, auth_ref: str, connect_timeout_seconds: int) -> None:
        kwargs: dict[str, Any] = {
            "servers": [nats_url],
            "connect_timeout": connect_timeout_seconds,
            "max_reconnect_attempts": 0,
        }
        if auth_ref and auth_ref.lower() not in {"none", "local-uat-auth-ref", "local-uat-redacted-ref"}:
            kwargs["token"] = auth_ref
        self._run(self._connect_impl(**kwargs))

    def subscribe(self, subject: str, handler: MessageHandler) -> None:
        async def _subscribe() -> None:
            async def _handler(msg: Any) -> None:
                try:
                    payload = json.loads(msg.data.decode("utf-8")) if msg.data else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = {"_decode_error": True}
                handler(msg.subject, payload if isinstance(payload, dict) else {"payload": payload})

            await self._nc.subscribe(subject, cb=_handler)
            await self._nc.flush()

        self._run(_subscribe())

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        async def _publish() -> None:
            await self._nc.publish(subject, json.dumps(payload, sort_keys=True).encode("utf-8"))
            await self._nc.flush()

        self._run(_publish())

    def drain(self) -> None:
        if self._nc is not None:
            self._run(self._nc.drain())

    def close(self) -> None:
        if self._nc is not None and not self._nc.is_closed:
            self._run(self._nc.close())
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=2)

    async def _connect_impl(self, **kwargs: Any) -> None:
        self._nc = await nats.connect(**kwargs)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop_thread is not None and self._loop_thread.is_alive():
            return self._loop
        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()

        def _run_loop() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=_run_loop, name="ResidentControllerNatsLoop", daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5)
        return self._loop

    def _run(self, coro: Any) -> Any:
        loop = self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop).result()


def run_start_once(
    *,
    config: dict[str, Any],
    broker: ResidentBrokerClient | None = None,
    lifecycle_provider: ResidentLifecycleProvider | None = None,
) -> ResidentStartOnceRuntimeResult:
    records: list[ResidentEvidenceRecord] = []
    errors: list[str] = []
    sequence = 0

    def record(record_type: str, payload: dict[str, Any]) -> str:
        nonlocal sequence
        sequence += 1
        event_time = _now()
        records.append(
            ResidentEvidenceRecord(
                sequence=sequence,
                record_type=record_type,
                event_time=event_time,
                payload={**payload, "not_business_completion": True},
            )
        )
        return event_time

    config_result = validate_resident_controller_config(config)
    record(
        "config_validation",
        {
            "valid": config_result.valid,
            "config_hash": config_result.config_hash,
            "live_runtime_allowed": config_result.live_runtime_allowed,
        },
    )
    if not config_result.valid:
        errors.extend(config_result.errors)

    controller = dict(config.get("controller") or {})
    broker_config = dict(config.get("broker") or {})
    subjects = dict(config.get("subjects") or {})
    runtimes = dict(config.get("runtimes") or {})
    policy_config = dict(config.get("policy") or {})
    evidence_config = dict(config.get("evidence") or {})
    uat_config = dict(config.get("uat") or {})
    run_id = str(controller.get("run_id") or controller.get("runtime_instance_id") or "")
    allowed_agents = [str(agent) for agent in runtimes.get("allowed_agents") or []]
    configured_wbs_id = _configured_wbs_id(controller.get("allowed_wbs_ids") or [])

    if controller.get("launch_mode") != "bounded_uat":
        errors.append("BOUNDED_UAT_LAUNCH_MODE_REQUIRED")
    if not controller.get("run_authorization_ref"):
        errors.append("MISSING_UAT_AUTHORIZATION")
    if not configured_wbs_id:
        errors.append("SUPPORTED_WBS_ID_NOT_AUTHORIZED")

    nats_url = _resolve_env_ref(broker_config.get("nats_url_ref"), field_name="broker.nats_url_ref", errors=errors)
    auth_ref = _resolve_env_ref(broker_config.get("auth_ref"), field_name="broker.auth_ref", errors=errors)
    _validate_uat_broker_url(
        nats_url,
        require_non_loopback=bool(policy_config.get("require_non_loopback_for_distributed_uat")),
        errors=errors,
    )

    status_state = "blocked" if errors else "starting"
    if errors:
        status = _status(status_state, False, False, "", evidence_config, event_timestamps={})
        return ResidentStartOnceRuntimeResult(
            accepted=False,
            daemon_started=False,
            service_state=status_state,
            errors=_dedupe(errors),
            evidence_records=records,
            status_snapshot=status,
        )

    client = broker or NatsResidentBrokerClient()
    lifecycle_provider = lifecycle_provider or BoundedUatResidentLifecycleProvider()
    observed: dict[str, set[str]] = {
        "registration": set(),
        "readiness": set(),
        "heartbeat": set(),
        "ack": set(),
        "progress": set(),
        "evidence": set(),
        "result_candidate": set(),
        "duplicate_suppression": set(),
        "offline": set(),
    }
    event_timestamps: dict[str, str] = {
        "registration_at": "",
        "readiness_at": "",
        "heartbeat_at": "",
        "assignment_published_at": "",
        "ack_at": "",
        "progress_at": "",
        "evidence_at": "",
        "result_candidate_at": "",
        "duplicate_replay_at": "",
        "duplicate_suppression_at": "",
        "drain_at": "",
    }
    published_assignments: list[PublishedAssignment] = []

    def handle_event(subject: str, payload: dict[str, Any]) -> None:
        family, agent_id = _event_family(subject, namespace=str(subjects.get("namespace")), run_id=run_id)
        if family not in observed:
            record("unclassified_event_observed", {"subject": _redact_subject(subject), "family": family})
            return
        if agent_id:
            observed[family].add(agent_id)
        duplicate_suppression = family == "evidence" and _is_duplicate_replay_suppression_evidence(payload)
        if duplicate_suppression and agent_id:
            observed["duplicate_suppression"].add(agent_id)
        event_time = record(
            _record_type_for_family(family),
            {
                "subject": _redact_subject(subject),
                "agent_id": agent_id,
                "payload_keys": sorted(payload),
                "candidate_evidence_only": family in {"ack", "progress", "evidence", "result_candidate"},
                "duplicate_replay_suppression": duplicate_suppression,
            },
        )
        timestamp_key = f"{family}_at" if family != "result_candidate" else "result_candidate_at"
        if timestamp_key in event_timestamps:
            event_timestamps[timestamp_key] = event_time
        if duplicate_suppression:
            event_timestamps["duplicate_suppression_at"] = event_time

    try:
        client.connect(
            nats_url=nats_url,
            auth_ref=auth_ref,
            connect_timeout_seconds=int(broker_config.get("connect_timeout_seconds") or 5),
        )
        for subject in _run_scoped_subscriptions(
            patterns=[str(pattern) for pattern in subjects.get("subscribe_allowlist") or []],
            namespace=str(subjects.get("namespace")),
            run_id=run_id,
        ):
            client.subscribe(subject, handle_event)
        record(
            "route_readiness",
            {
                "broker_connected": True,
                "subscriptions_ready": True,
                "service_state": "route_ready",
            },
        )
        subject_policy = ResidentControllerSubjectPolicy(
            namespace=str(subjects.get("namespace")),
            run_id=run_id,
            allowed_agents=allowed_agents,
            publish_allowlist=[str(pattern) for pattern in subjects.get("publish_allowlist") or []],
        )
        for agent_id in allowed_agents:
            _publish_allowed_command(
                client=client,
                subject_policy=subject_policy,
                command="controller_init",
                run_id=run_id,
                agent_id=agent_id,
                payload=_command_payload("controller_init", run_id, agent_id, controller),
                record=record,
                errors=errors,
            )

        if bool(uat_config.get("assignment_enabled")):
            _wait_for_assignment_readiness(
                observed=observed,
                allowed_agents=allowed_agents,
                max_runtime_seconds=float(uat_config.get("max_runtime_seconds", 5)),
            )
            for agent_id in allowed_agents:
                if agent_id not in observed["readiness"] or agent_id not in observed["heartbeat"]:
                    errors.append(f"ASSIGNMENT_READINESS_HEARTBEAT_NOT_OBSERVED: {agent_id}")
                    continue
                published = _publish_assignment(
                    client=client,
                    subject_policy=subject_policy,
                    run_id=run_id,
                    agent_id=agent_id,
                    controller=controller,
                    uat_config=uat_config,
                    wbs_id=configured_wbs_id,
                    lifecycle_provider=lifecycle_provider,
                    record=record,
                    errors=errors,
                )
                if published is not None:
                    published_assignments.append(published)
                    event_timestamps["assignment_published_at"] = published.published_at

        if published_assignments:
            _wait_for_candidate_observations(
                observed=observed,
                allowed_agents=[assignment.agent_id for assignment in published_assignments],
                timeout_seconds=_post_assignment_observation_timeout_seconds(uat_config, dict(config.get("recovery") or {})),
            )
            if observed["result_candidate"]:
                duplicate_replay_agents: list[str] = []
                for assignment in published_assignments:
                    duplicate_replay_at = _publish_duplicate_replay(
                        client=client,
                        subject_policy=subject_policy,
                        assignment=assignment,
                        record=record,
                        errors=errors,
                    )
                    if duplicate_replay_at:
                        event_timestamps["duplicate_replay_at"] = duplicate_replay_at
                        duplicate_replay_agents.append(assignment.agent_id)
                if duplicate_replay_agents:
                    _wait_for_duplicate_suppression(
                        observed=observed,
                        allowed_agents=duplicate_replay_agents,
                        timeout_seconds=_duplicate_replay_suppression_timeout_seconds(uat_config),
                    )
                    _require_duplicate_suppression(
                        observed=observed,
                        allowed_agents=duplicate_replay_agents,
                        errors=errors,
                    )
        else:
            _wait_for_runtime_window(float(uat_config.get("post_assignment_seconds", 0)))
        if bool(uat_config.get("assignment_enabled")):
            _require_candidate_observations(
                observed=observed,
                errors=errors,
                assignment_published=bool(published_assignments),
            )
        if not errors:
            for agent_id in allowed_agents:
                drain_at = _publish_allowed_command(
                    client=client,
                    subject_policy=subject_policy,
                    command="drain",
                    run_id=run_id,
                    agent_id=agent_id,
                    payload=_command_payload("drain", run_id, agent_id, controller),
                    record=record,
                    errors=errors,
                )
                if drain_at:
                    event_timestamps["drain_at"] = drain_at
            _wait_for_runtime_window(float(uat_config.get("post_drain_seconds", 0.5)))
            if not observed["offline"]:
                errors.append("OFFLINE_NOT_OBSERVED_AFTER_DRAIN")
            client.drain()
            record(
                "drain_offline",
                {
                    "drain_published": True,
                    "offline_observed_agents": sorted(observed["offline"]),
                },
            )
    except Exception as exc:  # noqa: BLE001 - fail closed with evidence
        errors.append(f"BROKER_RUNTIME_ERROR: {type(exc).__name__}")
    finally:
        try:
            client.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"BROKER_CLOSE_ERROR: {type(exc).__name__}")

    service_state = "offline" if not errors else "blocked"
    status = _status(
        service_state,
        broker_connected=not any(error.startswith("BROKER_RUNTIME_ERROR") for error in errors),
        subscriptions_ready=not errors,
        last_heartbeat_at=_now() if observed["heartbeat"] else "",
        evidence_config=evidence_config,
        event_timestamps=event_timestamps,
    )
    default_evidence_root = f"evidence/4.19/wbs-{configured_wbs_id or '7.19.15'}/resident-controller/RUN_ID"
    evidence_root = Path(str(evidence_config.get("root") or default_evidence_root).replace("RUN_ID", run_id))
    package = build_evidence_package(run_id=run_id, evidence_root=evidence_root, records=records, status_summary=status)
    errors.extend(package.errors)
    return ResidentStartOnceRuntimeResult(
        accepted=not errors,
        daemon_started=not errors,
        service_state=service_state,
        errors=_dedupe(errors),
        evidence_records=records,
        status_snapshot=status,
        evidence_package=package,
    )


def _publish_assignment(
    *,
    client: ResidentBrokerClient,
    subject_policy: ResidentControllerSubjectPolicy,
    run_id: str,
    agent_id: str,
    controller: dict[str, Any],
    uat_config: dict[str, Any],
    wbs_id: str,
    lifecycle_provider: ResidentLifecycleProvider,
    record: Callable[[str, dict[str, Any]], None],
    errors: list[str],
) -> PublishedAssignment | None:
    now_at = _now()
    assignment_id = str(uat_config.get("assignment_id") or f"{run_id}-assignment")
    idempotency_key = str(uat_config.get("idempotency_key") or f"{run_id}-idempotency")
    target_runtime_instance_id = str(uat_config.get("target_runtime_instance_id") or agent_id)
    lifecycle_decision, reservation_lease = lifecycle_provider.assignment_decision_and_lease(
        run_id=run_id,
        agent_id=agent_id,
        assignment_id=assignment_id,
        idempotency_key=idempotency_key,
        target_runtime_instance_id=target_runtime_instance_id,
        now_at=now_at,
    )
    request = ResidentControllerDispatchRequest(
        assignment_id=assignment_id,
        idempotency_key=idempotency_key,
        run_id=run_id,
        wbs_id=wbs_id,
        target_agent_id=agent_id,
        target_runtime_instance_id=target_runtime_instance_id,
        assignment_kind=str(uat_config.get("assignment_kind") or "non_business_probe"),
        command="bounded_assignment",
        source_authority_ref=str(controller.get("run_authorization_ref") or ""),
        no_go_scope_ref=f"no-go://wbs-{wbs_id}",
        lifecycle_decision_id=lifecycle_decision.decision_id if lifecycle_decision is not None else "",
        reservation_lease_id=reservation_lease.lease_id if reservation_lease is not None else "",
        not_business_completion=True,
    )
    subject = f"{subject_policy.namespace}.{run_id}.{agent_id}.assignment"
    subject_result = validate_publish_subject(subject, subject_policy)
    if not subject_result.accepted:
        errors.extend(subject_result.errors)
        return None
    dispatch_policy = ResidentControllerDispatchPolicy(
        dispatch_enabled=True,
        uat_authorized=True,
        allowed_wbs_ids={wbs_id},
    )
    if request.assignment_kind not in {
        "non_business_probe",
        "readiness_probe",
        "diagnostic_probe",
        "synthetic_business_command_acceptance",
    }:
        errors.append("BUSINESS_EXECUTION_NOT_AUTHORIZED")
        return None
    # Build a deterministic message id without letting dispatcher publish or claim completion.
    decision = evaluate_resident_dispatch(
        request=request,
        runtime=_runtime_record_for_assignment(agent_id=agent_id, request=request, wbs_id=wbs_id),
        subject_policy=subject_policy,
        policy=dispatch_policy,
        now_at=now_at,
        lifecycle_decision=lifecycle_decision,
        reservation_lease=reservation_lease,
    )
    if not decision.accepted:
        errors.extend(decision.errors)
        return None
    payload = {**request.to_dict(), "message_id": decision.message_id, "candidate_only": True}
    client.publish(subject, payload)
    published_at = record(
        "bounded_assignment_published",
        {
            "subject": _redact_subject(subject),
            "message_id": decision.message_id,
            "wbs_id": wbs_id,
            "no_go_scope_ref": request.no_go_scope_ref,
            "runtime_authority_scopes": [f"wbs://{wbs_id}"],
            "lifecycle_decision_id": request.lifecycle_decision_id,
            "reservation_lease_id": request.reservation_lease_id,
        },
    )
    return PublishedAssignment(agent_id=agent_id, subject=subject, payload=payload, published_at=published_at)


def _publish_duplicate_replay(
    *,
    client: ResidentBrokerClient,
    subject_policy: ResidentControllerSubjectPolicy,
    assignment: PublishedAssignment,
    record: Callable[[str, dict[str, Any]], str],
    errors: list[str],
) -> str:
    subject = f"{assignment.subject}.duplicate_replay"
    subject_result = validate_publish_subject(subject, subject_policy)
    if not subject_result.accepted:
        errors.extend(subject_result.errors)
        return ""
    payload = {
        **assignment.payload,
        "duplicate_replay": True,
        "duplicate_replay_of_subject": assignment.subject,
        "duplicate_replay_of_message_id": assignment.payload.get("message_id", ""),
        "not_business_completion": True,
        "candidate_only": True,
    }
    client.publish(subject, payload)
    return record(
        "duplicate_replay_published",
        {
            "subject": _redact_subject(subject),
            "original_subject": _redact_subject(assignment.subject),
            "assignment_id": assignment.payload.get("assignment_id", ""),
            "idempotency_key": assignment.payload.get("idempotency_key", ""),
            "duplicate_suppression_expected": True,
        },
    )


def _require_candidate_observations(
    *,
    observed: dict[str, set[str]],
    errors: list[str],
    assignment_published: bool,
) -> None:
    if not assignment_published:
        return
    if not observed["ack"]:
        errors.append("ACK_CANDIDATE_NOT_OBSERVED")
    if not observed["progress"]:
        errors.append("PROGRESS_CANDIDATE_NOT_OBSERVED")
    if not observed["evidence"]:
        errors.append("EVIDENCE_CANDIDATE_NOT_OBSERVED")
    if not observed["result_candidate"]:
        errors.append("RESULT_CANDIDATE_NOT_OBSERVED")


def _require_duplicate_suppression(
    *,
    observed: dict[str, set[str]],
    allowed_agents: list[str],
    errors: list[str],
) -> None:
    for agent in allowed_agents:
        if agent not in observed["duplicate_suppression"]:
            errors.append(f"DUPLICATE_REPLAY_SUPPRESSION_NOT_OBSERVED: {agent}")


def _runtime_record_for_assignment(*, agent_id: str, request: ResidentControllerDispatchRequest, wbs_id: str) -> Any:
    from nexus.mq.agent_registry import AgentRegistryRecord

    now = _now()
    return AgentRegistryRecord(
        agent_id=agent_id,
        runtime_instance_id=request.target_runtime_instance_id,
        role="implementation_agent",
        owner_principal_id=f"principal://{agent_id}",
        runtime_type="agent",
        channel_bindings=["nats"],
        capabilities=["controlled_uat_handoff_receive"],
        authority_scopes=[f"wbs://{wbs_id}"],
        allowed_task_boundaries=["non_business_probe"],
        initialization_status="ready",
        registry_status="active",
        presence_state="idle",
        heartbeat_ttl_seconds=30,
        last_heartbeat_at=now,
        current_assignment_refs=[],
        protocol_versions_supported=["4.19"],
        trust_material_ref=f"trust://{agent_id}",
        startup_packet_ref=f"startup://{agent_id}/{request.run_id}",
        readiness_evidence_ref=f"evidence://{agent_id}/readiness",
        startup_packet_expires_at=now,
        created_at=now,
        updated_at=now,
    )


def _publish_allowed_command(
    *,
    client: ResidentBrokerClient,
    subject_policy: ResidentControllerSubjectPolicy,
    command: str,
    run_id: str,
    agent_id: str,
    payload: dict[str, Any],
    record: Callable[[str, dict[str, Any]], None],
    errors: list[str],
) -> str:
    family = {"controller_init": "controller.init", "drain": "drain"}[command]
    subject = f"{subject_policy.namespace}.{run_id}.{agent_id}.{family}"
    subject_result = validate_publish_subject(subject, subject_policy)
    if not subject_result.accepted:
        errors.extend(subject_result.errors)
        return ""
    client.publish(subject, payload)
    return record(f"{command}_published", {"subject": _redact_subject(subject)})


def _configured_wbs_id(allowed_wbs_ids: Any) -> str:
    allowed = [str(wbs_id) for wbs_id in allowed_wbs_ids]
    for preferred in ("7.19.15.2", "7.19.15", "7.19.14.5"):
        if preferred in allowed and preferred in DEFAULT_ALLOWED_WBS_IDS:
            return preferred
    for wbs_id in allowed:
        if wbs_id in DEFAULT_ALLOWED_WBS_IDS:
            return wbs_id
    return ""


def _command_payload(command: str, run_id: str, agent_id: str, controller: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "4.19.resident_controller.command.v1",
        "command": command,
        "run_id": run_id,
        "target_agent_id": agent_id,
        "source_authority_ref": controller.get("run_authorization_ref"),
        "not_business_completion": True,
        "candidate_only": True,
    }


def _resolve_env_ref(value: Any, *, field_name: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.startswith("env:"):
        errors.append(f"ENV_REF_REQUIRED: {field_name}")
        return ""
    import os

    env_name = value.removeprefix("env:")
    resolved = os.environ.get(env_name)
    if resolved is None:
        errors.append(f"ENV_REF_NOT_SET: {field_name}")
        return ""
    return resolved


def _validate_uat_broker_url(nats_url: str, *, require_non_loopback: bool, errors: list[str]) -> None:
    if not nats_url:
        return
    parsed = urlparse(nats_url)
    if parsed.scheme != "nats":
        errors.append("NATS_URL_SCHEME_REQUIRED")
    if parsed.port == 4222:
        errors.append("PRODUCTION_OR_DEFAULT_NATS_PORT_NOT_AUTHORIZED_FOR_5B")
    if require_non_loopback and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        errors.append("LOOPBACK_BROKER_NOT_AUTHORIZED_FOR_DISTRIBUTED_UAT")


def _run_scoped_subscriptions(*, patterns: list[str], namespace: str, run_id: str) -> list[str]:
    scoped: list[str] = []
    prefix = f"{namespace}.*."
    for pattern in patterns:
        if pattern.startswith(prefix):
            suffix = pattern[len(prefix):]
            first_suffix_segment = suffix.split(".", 1)[0]
            if first_suffix_segment in {
                "registration",
                "readiness",
                "heartbeat",
                "ack",
                "progress",
                "evidence",
                "result_candidate",
                "offline",
            }:
                scoped.append(f"{namespace}.{run_id}.*.{suffix}")
            else:
                scoped.append(f"{namespace}.{run_id}.{suffix}")
        elif pattern.startswith(f"{namespace}.{run_id}."):
            scoped.append(pattern)
    return _dedupe(scoped)


def _event_family(subject: str, *, namespace: str, run_id: str) -> tuple[str, str]:
    parts = subject.split(".")
    namespace_parts = namespace.split(".")
    run_index = len(namespace_parts)
    agent_index = run_index + 1
    family_index = agent_index + 1
    if parts[:run_index] != namespace_parts or len(parts) <= family_index or parts[run_index] != run_id:
        return "", ""
    return parts[family_index], parts[agent_index]


def _record_type_for_family(family: str) -> str:
    if family in {"ack", "progress", "evidence", "result_candidate"}:
        if family == "result_candidate":
            return "result_candidate_observed"
        return f"{family}_candidate_observed"
    return f"{family}_observed"


def _wait_for_runtime_window(seconds: float) -> None:
    if seconds <= 0:
        return
    time.sleep(seconds)


def _wait_for_assignment_readiness(
    *,
    observed: dict[str, set[str]],
    allowed_agents: list[str],
    max_runtime_seconds: float,
) -> None:
    if not allowed_agents:
        return
    deadline = time.monotonic() + max(0.0, max_runtime_seconds)
    while time.monotonic() <= deadline:
        if any(agent in observed["readiness"] and agent in observed["heartbeat"] for agent in allowed_agents):
            return
        if max_runtime_seconds <= 0:
            return
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


def _wait_for_candidate_observations(
    *,
    observed: dict[str, set[str]],
    allowed_agents: list[str],
    timeout_seconds: float,
) -> None:
    if timeout_seconds <= 0 or not allowed_agents:
        return
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if _candidate_observations_complete(observed=observed, allowed_agents=allowed_agents):
            return
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


def _wait_for_duplicate_suppression(
    *,
    observed: dict[str, set[str]],
    allowed_agents: list[str],
    timeout_seconds: float,
) -> None:
    if timeout_seconds <= 0 or not allowed_agents:
        return
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if all(agent in observed["duplicate_suppression"] for agent in allowed_agents):
            return
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))


def _candidate_observations_complete(*, observed: dict[str, set[str]], allowed_agents: list[str]) -> bool:
    return all(
        agent in observed["ack"]
        and agent in observed["progress"]
        and agent in observed["evidence"]
        and agent in observed["result_candidate"]
        for agent in allowed_agents
    )


def _post_assignment_observation_timeout_seconds(uat_config: dict[str, Any], recovery_config: dict[str, Any] | None = None) -> float:
    configured = float(uat_config.get("post_assignment_observation_seconds") or 0)
    legacy_window = float(uat_config.get("post_assignment_seconds") or 0)
    recovery_window = float((recovery_config or {}).get("result_candidate_timeout_seconds") or 0)
    minimum_window = max(MIN_POST_ASSIGNMENT_OBSERVATION_SECONDS, recovery_window)
    if configured > 0:
        return max(configured, legacy_window, minimum_window)
    if legacy_window > 0:
        return max(legacy_window, minimum_window)
    return recovery_window


def _duplicate_replay_suppression_timeout_seconds(uat_config: dict[str, Any]) -> float:
    configured = float(uat_config.get("duplicate_replay_suppression_timeout_seconds") or 0)
    if configured > 0:
        return configured
    return DEFAULT_DUPLICATE_REPLAY_SUPPRESSION_TIMEOUT_SECONDS


def _is_duplicate_replay_suppression_evidence(payload: dict[str, Any]) -> bool:
    if payload.get("duplicate_replay_suppressed") is True:
        return True
    if payload.get("duplicate_suppressed") is True:
        return True
    error_code = str(payload.get("error_code") or "")
    errors = [str(error) for error in payload.get("errors") or []]
    return error_code == "DUPLICATE_ASSIGNMENT_SUPPRESSED" or "DUPLICATE_ASSIGNMENT_SUPPRESSED" in errors


def _status(
    service_state: str,
    broker_connected: bool,
    subscriptions_ready: bool,
    last_heartbeat_at: str,
    evidence_config: dict[str, Any],
    event_timestamps: dict[str, str],
) -> dict[str, Any]:
    return build_status_snapshot(
        service_state=service_state,
        broker_connected=broker_connected,
        subscriptions_ready=subscriptions_ready,
        last_heartbeat_at=event_timestamps.get("heartbeat_at") or last_heartbeat_at,
        pending_assignments=[],
        evidence_root=str(evidence_config.get("root") or ""),
        event_timestamps=event_timestamps,
    )


def _redact_subject(subject: str) -> str:
    return subject


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_after(value: str, *, seconds: int) -> str:
    try:
        base = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        base = datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(seconds=seconds)).isoformat()


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped
