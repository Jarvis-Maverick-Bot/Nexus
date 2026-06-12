from __future__ import annotations

from nexus.governance.source_authority import (
    REQUIRED_PR9_MERGE_COMMIT,
    REQUIRED_SLICE002_AUTHORITY_COMMITS,
    Slice002AuthorityManifest,
    verify_slice002_source_authority,
)

from ._evidence import write_evidence


def valid_slice002_manifest(**overrides: object) -> Slice002AuthorityManifest:
    values = {
        "shared_docs_remote": "git@github.com:Nova-Mini/Nova-Jarvis-Shared-Docs.git",
        "source_root": "D:\\Nova-Jarvis-Shared-Docs",
        "wbs_version": "V0.6",
        "l1112_status": "accepted",
        "slice002_package_review_decision": "APPROVE_SLICE_002_TASK_PACKAGE",
        "required_shared_docs_commits": REQUIRED_SLICE002_AUTHORITY_COMMITS,
        "pr9_merge_commit": REQUIRED_PR9_MERGE_COMMIT,
        "slice001_evidence_status": "accepted",
        "slice001_no_nexus_mq_imports": True,
    }
    values.update(overrides)
    return Slice002AuthorityManifest(**values)


def test_accepts_slice002_source_authority() -> None:
    result = verify_slice002_source_authority(valid_slice002_manifest())

    assert result.accepted is True
    assert result.error_code is None
    write_evidence("source/source-authority.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_requires_nova_package_review_commit_3018953() -> None:
    commits = tuple(c for c in REQUIRED_SLICE002_AUTHORITY_COMMITS if c != "3018953")

    result = verify_slice002_source_authority(valid_slice002_manifest(required_shared_docs_commits=commits))

    assert result.accepted is False
    assert result.error_code == "ERR_STALE_SOURCE_AUTHORITY"
    assert result.missing_commits == ("3018953",)
    write_evidence("source/stale-source-block.json", result.to_evidence(), slice_id="l1gov-slice-002")


def test_requires_pr9_merge_commit() -> None:
    result = verify_slice002_source_authority(valid_slice002_manifest(pr9_merge_commit="1a118ce"))

    assert result.accepted is False
    assert result.error_code == "ERR_STALE_SOURCE_AUTHORITY"
    assert result.expected == REQUIRED_PR9_MERGE_COMMIT
    assert result.observed == "1a118ce"


def test_requires_slice001_import_scan_evidence() -> None:
    result = verify_slice002_source_authority(valid_slice002_manifest(slice001_no_nexus_mq_imports=False))

    assert result.accepted is False
    assert result.error_code == "ERR_NO_GO_BOUNDARY"
    assert result.message == "accepted Slice 001 evidence no longer proves no Nexus MQ imports"
