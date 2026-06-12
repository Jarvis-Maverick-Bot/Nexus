from __future__ import annotations

from nexus.governance.source_authority import (
    REQUIRED_AUTHORITY_COMMITS,
    SourceAuthorityManifest,
    verify_source_authority,
)

from ._evidence import write_evidence


def valid_manifest(**overrides: object) -> SourceAuthorityManifest:
    values = {
        "parent_solution_design_version": "V0.8.5",
        "wbs_version": "V0.6",
        "accepted_subtopics": tuple(f"L1.11.{i}" for i in range(1, 11)),
        "integration_review_version": "V0.2",
        "integration_review_status": "Accepted",
        "final_assessment_disposition": "READY_FOR_IMPLEMENTATION_TASK_PACKAGE_PREPARATION",
        "direct_coding_disposition": "NO_GO_FOR_DIRECT_CODING",
        "slice001_package_decision": "APPROVE_FIRST_SLICE_TASK_PACKAGE",
        "slice001_authorization_decision": "AUTHORIZE_SLICE_001_IMPLEMENTATION",
        "required_commits": REQUIRED_AUTHORITY_COMMITS,
        "shared_docs_remote": "git@github.com:Nova-Mini/Nova-Jarvis-Shared-Docs.git",
        "source_root": "D:\\Nova-Jarvis-Shared-Docs",
    }
    values.update(overrides)
    return SourceAuthorityManifest(**values)


def test_accepts_wbs_v0_6_manifest() -> None:
    result = verify_source_authority(valid_manifest())

    assert result.accepted is True
    assert result.error_code is None
    path = write_evidence(
        "source/source-authority.json",
        {"accepted": result.accepted, "required_commits": list(REQUIRED_AUTHORITY_COMMITS)},
    )
    assert path.exists()


def test_rejects_wbs_v0_4_manifest() -> None:
    result = verify_source_authority(valid_manifest(wbs_version="V0.4"))

    assert result.accepted is False
    assert result.error_code == "ERR_STALE_SOURCE_AUTHORITY"
    assert result.expected == "V0.6"
    assert result.observed == "V0.4"
    write_evidence("source/stale-source-block.json", result.to_evidence())


def test_requires_final_assessment_commit_1c29365() -> None:
    commits = tuple(c for c in REQUIRED_AUTHORITY_COMMITS if c != "1c29365")

    result = verify_source_authority(valid_manifest(required_commits=commits))

    assert result.accepted is False
    assert result.error_code == "ERR_STALE_SOURCE_AUTHORITY"
    assert result.missing_commits == ("1c29365",)
    write_evidence("source/missing-final-assessment.json", result.to_evidence())


def test_requires_slice001_authorization_commit_f9eaa5b() -> None:
    commits = tuple(c for c in REQUIRED_AUTHORITY_COMMITS if c != "f9eaa5b")

    result = verify_source_authority(valid_manifest(required_commits=commits))

    assert result.accepted is False
    assert result.error_code == "ERR_STALE_SOURCE_AUTHORITY"
    assert result.missing_commits == ("f9eaa5b",)
