"""
Foundation Review Executor — Doctrine-Driven Reasoning Producer
Jarvis reviews Nova's Foundation draft and returns DomainResult.

Pure reasoning producer:
- Loads doctrine + draft
- Produces doctrine-driven judgment
- Returns DomainResult

Does NOT: send NATS messages, update state, notify.
Caller (CollabHandler pipeline) owns message sending and state update.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from governance.collab.runtime_contract_map import DomainResult


# Paths for doctrine loading — resolved from V2.0 shared drive structure
_SHARED_ROOT = Path(r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0")

# macOS sharefolder mount base — convert to sharefolder path for Windows/Unix cross-compatibility
_MACOS_SHAREFOLDER_BASE = "/Users/alex/Nova-Jarvis-Shared"
_SHAREFOLDER_BASE = r"\\192.168.31.124\Nova-Jarvis-Shared"


def _to_sharefolder_path(artifact_path: str) -> str:
    r"""
    Convert macOS local sharefolder path to Windows/Unix sharefolder path.
    e.g. /Users/alex/Nova-Jarvis-Shared/... -> \\192.168.31.124\Nova-Jarvis-Shared\...

    Also handles already-sharefolder paths (no-op).
    """
    if not artifact_path:
        return artifact_path
    if artifact_path.startswith(_SHAREFOLDER_BASE.replace('\\\\', '\\')):
        # Already in sharefolder format
        return artifact_path
    if artifact_path.startswith(_MACOS_SHAREFOLDER_BASE):
        return artifact_path.replace(_MACOS_SHAREFOLDER_BASE, _SHAREFOLDER_BASE.replace('\\', '\\\\'))
    return artifact_path
_FOUNDATION_BASELINE = _SHARED_ROOT / "01-release-definition" / "V2_0_FOUNDATION_V0_2.md"
_SCOPE_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_SCOPE_V0_2.md"
_PRD_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_PRD_V0_2.md"


def _load_doctrine(doctrine_loading_set: list) -> dict:
    """
    Load doctrine files from paths in doctrine_loading_set.
    Returns doctrine_snapshot dict.
    Raises RuntimeError if ALL doctrine files fail to load.
    Partial failures are logged but allowed (doctrine_loaded=False returned).
    """
    loaded = {}
    errors = []

    path_map = {
        "v2_0_foundation_baseline": _FOUNDATION_BASELINE,
        "v2_0_scope": _SCOPE_DOC,
        "v2_0_prd": _PRD_DOC,
    }

    for name in doctrine_loading_set:
        path = path_map.get(name)
        if not path:
            errors.append(f"no path mapping for doctrine: {name}")
            continue
        if not path.exists():
            errors.append(f"doctrine file not found: {path}")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded[name] = f.read()
        except Exception as e:
            errors.append(f"failed to load {name}: {e}")

    if not loaded:
        raise RuntimeError(f"doctrine_load_failed: all files failed — {errors}")

    return {
        "doctrine_loaded": True,
        "doctrine_snapshot": loaded,
        "warnings": errors if errors else None,
        "loaded_at": datetime.now(timezone.utc).isoformat()
    }


def _load_nova_draft(artifact_path: str) -> Tuple[bool, str, Optional[str]]:
    r"""Load Nova's Foundation draft from artifact_path.

    Handles cross-platform path conversion:
    - macOS /Users/alex/... -> \\192.168.31.124\Nova-Jarvis-Shared\...
    - Already-sharefolder paths pass through unchanged
    """
    if not artifact_path:
        return False, "", "artifact_path is empty"
    # Convert macOS local path to sharefolder path
    sharefolder_path = _to_sharefolder_path(artifact_path)
    path = Path(sharefolder_path)
    if not path.exists():
        return False, "", f"draft file not found: {sharefolder_path}"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return True, content, None
    except Exception as e:
        return False, "", f"failed to read draft: {e}"


def _extract_sections(text: str) -> Dict[str, str]:
    """Extract markdown sections from text. Returns {section_name: section_content}."""
    sections = {}
    if not text:
        return sections
    lines = text.split('\n')
    current_heading = None
    current_content = []
    for line in lines:
        m = re.match(r'^##?\s+(.+)$', line)
        if m:
            if current_heading:
                sections[current_heading] = '\n'.join(current_content).strip()
            current_heading = m.group(1).strip()
            current_content = []
        else:
            current_content.append(line)
    if current_heading:
        sections[current_heading] = '\n'.join(current_content).strip()
    return sections


def _produce_review_judgment(
    collab_id: str,
    draft_content: str,
    doctrine_snapshot: dict,
    review_scope: str
) -> Tuple[str, str]:
    """
    Doctrine-driven review judgment.
    Compares Nova's draft against three doctrine sources and produces analysis.
    """
    baseline = doctrine_snapshot.get("v2_0_foundation_baseline", "")
    scope_doc = doctrine_snapshot.get("v2_0_scope", "")
    prd_doc = doctrine_snapshot.get("v2_0_prd", "")

    baseline_sections = _extract_sections(baseline)
    scope_sections = _extract_sections(scope_doc)
    prd_sections = _extract_sections(prd_doc)

    draft_sections = _extract_sections(draft_content)
    draft_len = len(draft_content) if draft_content else 0

    # Baseline alignment check
    baseline_checks = []
    for bs_name, bs_content in baseline_sections.items():
        if len(bs_content) < 20:
            continue
        draft_lower = draft_content.lower()
        keywords = [w for w in bs_name.lower().split() if len(w) > 3]
        matched = any(kw in draft_lower for kw in keywords) if keywords else False
        baseline_checks.append({"doctrine_section": bs_name, "present_in_draft": matched, "chars": len(bs_content)})

    baseline_covered = sum(1 for c in baseline_checks if c["present_in_draft"])
    baseline_total = len(baseline_checks)

    # Scope coverage check
    scope_checks = []
    for sc_name, sc_content in scope_sections.items():
        if len(sc_content) < 20:
            continue
        draft_lower = draft_content.lower()
        keywords = [w for w in sc_name.lower().split() if len(w) > 3]
        matched = any(kw in draft_lower for kw in keywords) if keywords else False
        scope_checks.append({"doctrine_section": sc_name, "covered_in_draft": matched, "chars": len(sc_content)})

    scope_covered = sum(1 for c in scope_checks if c["covered_in_draft"])
    scope_total = len(scope_checks)

    # PRD requirement coverage
    prd_checks = []
    for pr_name, pr_content in prd_sections.items():
        if len(pr_content) < 30:
            continue
        requirement_phrases = [
            re.sub(r'^[\s\-\*]+', '', line).strip()
            for line in pr_content.split('\n')
            if len(line.strip()) > 10 and len(line.strip()) < 100
        ]
        matched_count = sum(
            1 for phrase in requirement_phrases
            if phrase.lower() in draft_content.lower()
        )
        coverage_pct = (matched_count / len(requirement_phrases) * 100) if requirement_phrases else 0
        prd_checks.append({
            "prd_section": pr_name,
            "requirements_in_section": len(requirement_phrases),
            "requirements_matched": matched_count,
            "coverage_pct": round(coverage_pct, 1)
        })

    prd_total_requirements = sum(c["requirements_in_section"] for c in prd_checks)
    prd_matched_requirements = sum(c["requirements_matched"] for c in prd_checks)
    prd_coverage_pct = (prd_matched_requirements / prd_total_requirements * 100) if prd_total_requirements else 0

    # Determine review_result
    baseline_ok = baseline_covered / baseline_total >= 0.6 if baseline_total else False
    scope_ok = scope_covered / scope_total >= 0.5 if scope_total else False
    prd_ok = prd_coverage_pct >= 40 if prd_total_requirements else False

    if baseline_ok and scope_ok and prd_ok:
        review_result = "approved"
    elif baseline_ok and (scope_ok or prd_ok):
        review_result = "revision_required"
    else:
        review_result = "blocked"

    # Build judgment report
    judgment = f"""# Foundation Review Judgment

**Collab ID:** {collab_id}
**Review Scope:** {review_scope}
**Reviewed at:** {datetime.now(timezone.utc).isoformat()}
**Method:** Doctrine-driven analysis (baseline + scope + PRD comparison)

---

## Baseline Alignment ({baseline_covered}/{baseline_total} sections covered)

| Doctrine Section | Present in Draft |
|------------------|-----------------|
"""
    for c in baseline_checks:
        status = "YES" if c["present_in_draft"] else "NO"
        judgment += f"| {c['doctrine_section']} | {status} |\n"

    judgment += f"\n**Baseline coverage: {baseline_covered}/{baseline_total} ({baseline_covered/baseline_total*100:.0f}%)**\n\n"

    judgment += f"""## Scope Coverage ({scope_covered}/{scope_total} sections addressed)

| Doctrine Section | Addressed in Draft |
|------------------|-------------------|
"""
    for c in scope_checks:
        status = "YES" if c["covered_in_draft"] else "NO"
        judgment += f"| {c['doctrine_section']} | {status} |\n"

    judgment += f"\n**Scope coverage: {scope_covered}/{scope_total} ({scope_covered/scope_total*100:.0f}%)**\n\n"

    judgment += f"""## PRD Requirement Coverage ({prd_matched_requirements}/{prd_total_requirements} requirements matched)

| PRD Section | Requirements | Matched | Coverage |
|-------------|--------------|---------|----------|
"""
    for c in prd_checks:
        judgment += f"| {c['prd_section']} | {c['requirements_in_section']} | {c['requirements_matched']} | {c['coverage_pct']:.0f}% |\n"

    judgment += f"\n**Overall PRD coverage: {prd_matched_requirements}/{prd_total_requirements} ({prd_coverage_pct:.0f}%)**\n\n"

    judgment += f"""## Overall Assessment

| Dimension | Threshold | Actual | Result |
|-----------|-----------|--------|--------|
| Baseline alignment | >=60% | {baseline_covered/baseline_total*100:.0f}% | {'PASS' if baseline_ok else 'FAIL'} |
| Scope coverage | >=50% | {scope_covered/scope_total*100:.0f}% | {'PASS' if scope_ok else 'FAIL'} |
| PRD requirements | >=40% | {prd_coverage_pct:.0f}% | {'PASS' if prd_ok else 'FAIL'} |

---

**Review Result: {review_result.upper()}**

Draft length: {draft_len} chars

"""
    if review_result == 'approved':
        judgment += "The draft adequately covers the V2.0 Foundation baseline, addresses core scope areas, and satisfies minimum PRD requirements. Ready for progression."
    elif review_result == 'revision_required':
        gaps = []
        if not baseline_ok:
            gaps.append(f"baseline ({baseline_covered/baseline_total*100:.0f}% < 60%)")
        if not scope_ok:
            gaps.append(f"scope ({scope_covered/scope_total*100:.0f}% < 50%)")
        if not prd_ok:
            gaps.append(f"PRD ({prd_coverage_pct:.0f}% < 40%)")
        judgment += f"Revision needed — gaps in: {', '.join(gaps)}. Please address these areas before re-submission."
    else:
        judgment += "Foundation draft has critical deficiencies across multiple doctrine dimensions. Significant rework required before further review."

    judgment += "\n\n*Generated by Nexus Governed Execution Loop — Doctrine-driven review*\n"

    return review_result, judgment


async def execute_review(
    handler: 'CollabHandler',
    collab_id: str,
    artifact_path: str,
    review_scope: str,
    doctrine_loading_set: list
) -> DomainResult:
    """
    Execute the Foundation review task (doctrine-driven reasoning producer).

    Pure reasoning: loads doctrine + draft, produces judgment.
    Returns DomainResult on success.
    Raises RuntimeError on doctrine_load_failed or draft_load_failed.

    Does NOT: send NATS messages, update state, notify.
    Caller (CollabHandler pipeline) owns those.
    """
    handler._log("EXEC", f"[{collab_id}] starting doctrine-driven foundation_review")

    # 1. Load doctrine — returns dict with doctrine_loaded status
    doctrine_result = _load_doctrine(doctrine_loading_set)
    if not doctrine_result.get("doctrine_loaded"):
        # Doctrine load failure — return revision_required DomainResult
        # This is a business-level outcome, not an exception
        handler._log("ERROR", f"[{collab_id}] doctrine_load_failed: {doctrine_result.get('errors')}")
        return DomainResult(
            message_type='review_response',
            collab_id=collab_id,
            from_='jarvis',
            result='revision_required',
            notes=f"Review cannot proceed: doctrine files unavailable — {doctrine_result.get('errors')}",
            workflow='v2_0',
            stage='foundation_create_review'
        )
    handler._log("EXEC", f"[{collab_id}] doctrine loaded OK: {list(doctrine_result.get('doctrine_snapshot', {}).keys())}")

    # 2. Load Nova's draft — return revision_required DomainResult on failure
    loaded, draft_content, error = _load_nova_draft(artifact_path)
    if not loaded:
        # Draft load failure — return revision_required DomainResult
        # Pipeline will send review_response to Nova with revision_required
        handler._log("ERROR", f"[{collab_id}] draft_load_failed: {error}")
        return DomainResult(
            message_type='review_response',
            collab_id=collab_id,
            from_='jarvis',
            result='revision_required',
            notes=f"Review cannot proceed: draft not found at {artifact_path}",
            workflow='v2_0',
            stage='foundation_create_review'
        )

    handler._log("EXEC", f"[{collab_id}] Nova draft loaded: {len(draft_content)} chars")

    # 3. Produce doctrine-driven review judgment
    review_result_str, judgment = _produce_review_judgment(
        collab_id,
        draft_content,
        doctrine_result.get("doctrine_snapshot", {}),
        review_scope
    )
    handler._log("EXEC", f"[{collab_id}] review judgment produced: {review_result_str}")

    # 4. Save judgment artifact
    repo_root = Path(__file__).parent.parent.parent
    judgment_path = repo_root / "governance" / "docs" / f"review_{collab_id}.md"
    try:
        judgment_path.parent.mkdir(parents=True, exist_ok=True)
        with open(judgment_path, 'w', encoding='utf-8') as f:
            f.write(judgment)
        handler._log("EXEC", f"[{collab_id}] review judgment written: {judgment_path}")
    except Exception as e:
        handler._log("ERROR", f"[{collab_id}] failed to write review judgment: {e}")
        judgment_path = None

    handler._log("EXEC", f"[{collab_id}] doctrine-driven foundation_review COMPLETE — result={review_result_str}")

    # Return DomainResult — pipeline expects DomainResult
    return DomainResult(
        message_type='review_response',
        collab_id=collab_id,
        from_='jarvis',
        result=review_result_str,
        notes=judgment,
        judgment_path=str(judgment_path) if judgment_path else '',
        workflow='v2_0',
        stage='foundation_create_review'
    )
