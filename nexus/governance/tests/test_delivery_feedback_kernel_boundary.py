from __future__ import annotations

from dataclasses import replace

from nexus.governance.errors import ErrorCode

from .fixtures.delivery_feedback import valid_record_delivery_command
from .test_delivery_feedback_service_contract import delivery_service, kernel_ready_for_delivery


def test_delivery_kernel_boundary_rejects_boolean_expected_version_without_append() -> None:
    kernel = kernel_ready_for_delivery()
    command = replace(valid_record_delivery_command(), expected_version=True)
    command.payload["expected_kernel_version"] = True

    response = delivery_service(kernel=kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.DELIVERY_FEEDBACK_COMMAND_INVALID
    assert len(kernel.records) == 0


def test_delivery_kernel_boundary_rejects_stale_version_without_append() -> None:
    kernel = kernel_ready_for_delivery()
    command = replace(valid_record_delivery_command(), expected_version=99)
    command.payload["expected_kernel_version"] = 99

    response = delivery_service(kernel=kernel).handle(command)

    assert response.accepted is False
    assert response.error_code == ErrorCode.STALE_EXPECTED_VERSION
    assert len(kernel.records) == 0


def test_delivery_kernel_boundary_replays_same_idempotency_key() -> None:
    kernel = kernel_ready_for_delivery()
    service = delivery_service(kernel=kernel)
    command = valid_record_delivery_command()

    first = service.handle(command)
    second = service.handle(command)

    assert first.accepted is True
    assert second.accepted is True
    assert second.record_ref == first.record_ref
    assert len(kernel.records) == 1


def test_delivery_kernel_boundary_rejects_idempotency_key_reuse() -> None:
    kernel = kernel_ready_for_delivery()
    service = delivery_service(kernel=kernel)
    command = valid_record_delivery_command()
    first = service.handle(command)
    reused = replace(command, payload={**command.payload, "projection_type": "changed"})

    second = service.handle(reused)

    assert first.accepted is True
    assert second.accepted is False
    assert second.error_code == ErrorCode.IDEMPOTENCY_KEY_REUSE
    assert len(kernel.records) == 1
