"""Persistence adapter for structured task records using existing phase5 store."""

from __future__ import annotations

from typing import Optional

from nexus.mq.durable_state import DurableStateStore, Phase5DurableRecord
from nexus.mq.agent_registry_events import secret_material_errors


def write_structured_task_record(
    store: DurableStateStore,
    *,
    family: str,
    status: str,
    payload: dict,
    workflow_instance_id: Optional[str] = None,
    target_ref: Optional[str] = None,
    authority_wait_id: Optional[str] = None,
    related_record_id: Optional[str] = None,
    dedupe_key: Optional[str] = None,
) -> Phase5DurableRecord:
    errors = secret_material_errors(payload, path="structured_task_record")
    if errors:
        raise ValueError(";".join(errors))
    return store.create_phase5_durable_record(
        family=family,
        status=status,
        payload={**payload, "not_business_completion": True},
        workflow_instance_id=workflow_instance_id,
        target_ref=target_ref,
        authority_wait_id=authority_wait_id,
        related_record_id=related_record_id,
        dedupe_key=dedupe_key,
    )


def list_structured_task_records(
    store: DurableStateStore,
    *,
    family: Optional[str] = None,
    workflow_instance_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Phase5DurableRecord]:
    return store.list_phase5_durable_records(
        family=family,
        workflow_instance_id=workflow_instance_id,
        status=status,
    )
