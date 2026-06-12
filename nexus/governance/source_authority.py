from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_AUTHORITY_COMMITS: tuple[str, ...] = (
    "7e2774d",
    "1c29365",
    "fce663a",
    "70ba8aa",
    "4dfd3d8",
    "f9eaa5b",
)

REQUIRED_SUBTOPICS: tuple[str, ...] = tuple(f"L1.11.{i}" for i in range(1, 11))
REQUIRED_SHARED_DOCS_REMOTE = "git@github.com:Nova-Mini/Nova-Jarvis-Shared-Docs.git"
REQUIRED_SHARED_DOCS_ROOT_MARKER = "nova-jarvis-shared-docs"


@dataclass(frozen=True)
class SourceAuthorityManifest:
    parent_solution_design_version: str
    wbs_version: str
    accepted_subtopics: tuple[str, ...]
    integration_review_version: str
    integration_review_status: str
    final_assessment_disposition: str
    direct_coding_disposition: str
    slice001_package_decision: str
    slice001_authorization_decision: str
    required_commits: tuple[str, ...]
    shared_docs_remote: str
    source_root: str


@dataclass(frozen=True)
class SourceAuthorityResult:
    accepted: bool
    error_code: str | None = None
    expected: str | None = None
    observed: str | None = None
    missing_commits: tuple[str, ...] = ()
    message: str = ""

    def to_evidence(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "error_code": self.error_code,
            "expected": self.expected,
            "message": self.message,
            "missing_commits": list(self.missing_commits),
            "observed": self.observed,
        }


def verify_source_authority(manifest: SourceAuthorityManifest) -> SourceAuthorityResult:
    if manifest.shared_docs_remote.strip() != REQUIRED_SHARED_DOCS_REMOTE:
        return _stale(
            REQUIRED_SHARED_DOCS_REMOTE,
            manifest.shared_docs_remote,
            "Shared Docs remote mismatch",
        )
    if not _is_verified_shared_docs_source_root(manifest.source_root):
        return _stale(
            "verified Shared Docs Git clone/worktree",
            manifest.source_root,
            "source root is not a verified Shared Docs Git clone/worktree",
        )
    if manifest.parent_solution_design_version != "V0.8.5":
        return _stale("V0.8.5", manifest.parent_solution_design_version, "parent solution version mismatch")
    if manifest.wbs_version != "V0.6":
        return _stale("V0.6", manifest.wbs_version, "WBS version mismatch")
    if tuple(manifest.accepted_subtopics) != REQUIRED_SUBTOPICS:
        return _stale(str(REQUIRED_SUBTOPICS), str(tuple(manifest.accepted_subtopics)), "accepted subtopic set mismatch")
    if manifest.integration_review_version != "V0.2" or manifest.integration_review_status != "Accepted":
        observed = f"{manifest.integration_review_version}/{manifest.integration_review_status}"
        return _stale("V0.2/Accepted", observed, "integration review mismatch")
    if manifest.final_assessment_disposition != "READY_FOR_IMPLEMENTATION_TASK_PACKAGE_PREPARATION":
        return _stale(
            "READY_FOR_IMPLEMENTATION_TASK_PACKAGE_PREPARATION",
            manifest.final_assessment_disposition,
            "final assessment disposition mismatch",
        )
    if manifest.direct_coding_disposition != "NO_GO_FOR_DIRECT_CODING":
        return SourceAuthorityResult(
            False,
            "ERR_NO_GO_BOUNDARY",
            expected="NO_GO_FOR_DIRECT_CODING",
            observed=manifest.direct_coding_disposition,
            message="direct coding disposition mismatch",
        )
    if manifest.slice001_package_decision != "APPROVE_FIRST_SLICE_TASK_PACKAGE":
        return _stale(
            "APPROVE_FIRST_SLICE_TASK_PACKAGE",
            manifest.slice001_package_decision,
            "slice 001 package decision mismatch",
        )
    if manifest.slice001_authorization_decision != "AUTHORIZE_SLICE_001_IMPLEMENTATION":
        return _stale(
            "AUTHORIZE_SLICE_001_IMPLEMENTATION",
            manifest.slice001_authorization_decision,
            "slice 001 authorization decision mismatch",
        )
    missing = tuple(commit for commit in REQUIRED_AUTHORITY_COMMITS if commit not in manifest.required_commits)
    if missing:
        return SourceAuthorityResult(
            False,
            "ERR_STALE_SOURCE_AUTHORITY",
            expected=",".join(REQUIRED_AUTHORITY_COMMITS),
            observed=",".join(manifest.required_commits),
            missing_commits=missing,
            message="required authority commits missing",
        )
    return SourceAuthorityResult(True, message="source authority accepted for Slice 001")


def _stale(expected: str, observed: str, message: str) -> SourceAuthorityResult:
    return SourceAuthorityResult(
        False,
        "ERR_STALE_SOURCE_AUTHORITY",
        expected=expected,
        observed=observed,
        message=message,
    )


def _is_verified_shared_docs_source_root(source_root: str) -> bool:
    normalized = source_root.strip().replace("/", "\\")
    lowered = normalized.lower()
    if not normalized:
        return False
    if lowered.startswith("\\\\") or lowered.startswith("smb:\\\\"):
        return False
    return REQUIRED_SHARED_DOCS_ROOT_MARKER in lowered
