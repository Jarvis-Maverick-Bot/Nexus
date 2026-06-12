from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.workspace_init import validate_template_profile

from ._evidence import write_evidence
from .fixtures.workspace_init import valid_profile_selection, valid_template_set


def test_approved_template_profile_is_accepted() -> None:
    result = validate_template_profile(valid_profile_selection(), valid_template_set())

    assert result.accepted is True
    assert result.error_code is None
    write_evidence("workspace/template-valid.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_unknown_template_profile_blocks_workspace_init() -> None:
    result = validate_template_profile(
        valid_profile_selection(profile_source_ref="workspace-template:unknown:v1"),
        valid_template_set(),
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_TEMPLATE_INVALID


def test_template_trim_rule_cannot_remove_required_governance_surface() -> None:
    result = validate_template_profile(
        valid_profile_selection(trim_rules_applied=("evidence_path",)),
        valid_template_set(trim_rules=("evidence_path",)),
    )

    assert result.accepted is False
    assert result.error_code == ErrorCode.WORKSPACE_TEMPLATE_INVALID
    assert result.blocked_reasons == ("required governance surface cannot be trimmed: evidence_path",)
    write_evidence("workspace/template-trim-block.json", result.to_evidence(), slice_id="l1gov-slice-002")
