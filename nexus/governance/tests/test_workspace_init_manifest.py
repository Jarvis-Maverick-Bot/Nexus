from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.workspace_init import validate_workspace_manifest

from ._evidence import write_evidence
from .fixtures.workspace_init import init_item, valid_manifest, valid_surface_index


def test_valid_workspace_manifest_produces_validation_evidence() -> None:
    result = validate_workspace_manifest(valid_manifest())

    assert result.accepted is True
    assert result.error_code is None
    assert result.missing_paths == ()
    write_evidence("workspace/manifest-valid.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_manifest_missing_required_governance_path_blocks_validation() -> None:
    surface_index = valid_surface_index(decision_log_path="")
    manifest = valid_manifest(surface_index=surface_index, created_paths=surface_index.required_paths())

    result = validate_workspace_manifest(manifest)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_MANIFEST_INVALID
    assert "decision_log_path" in result.missing_paths
    write_evidence("workspace/manifest-missing-path.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_seed_or_stub_outputs_cannot_self_authorize() -> None:
    manifest = valid_manifest(seed_items=(init_item("ProjectCharterStub", "approved"),))

    result = validate_workspace_manifest(manifest)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_MANIFEST_INVALID
    assert result.invalid_items == ("projectcharterstub-ws-421",)
    write_evidence("workspace/seed-status-block.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_planning_placeholder_rejects_planning_content() -> None:
    manifest = valid_manifest(
        seed_items=(
            init_item(
                "PlanningSurfacePlaceholder",
                "structural",
                scope_baseline="not allowed in Slice 002",
            ),
        )
    )

    result = validate_workspace_manifest(manifest)

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_MANIFEST_INVALID
    assert result.blocked_reasons == ("planning content is out of scope for Workspace Init",)
