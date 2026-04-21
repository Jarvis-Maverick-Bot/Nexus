"""
Foundation Review Executor — Option B (near-term)
Jarvis reviews Nova's Foundation draft and returns review judgment to Nova.

Doctrine-driven review: draft is judged against loaded doctrine files
(baseline, scope, PRD), not by structural heuristics alone.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple


# Paths for doctrine loading — resolved from V2.0 shared drive structure
_SHARED_ROOT = Path(r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0")
_FOUNDATION_BASELINE = _SHARED_ROOT / "01-release-definition" / "V2_0_FOUNDATION_V0_2.md"
_SCOPE_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_SCOPE_V0_2.md"
_PRD_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_PRD_V0_2.md"


def _load_doctrine(doctrine_loading_set: list) -> dict:
    """
    Load doctrine files from paths in doctrine_loading_set.
    Returns doctrine_snapshot dict. Missing files are logged as warnings, not hard errors.
    """
    loaded = {}
    warnings = []

    path_map = {
        "v2_0_foundation_baseline": _FOUNDATION_BASELINE,
        "v2_0_scope": _SCOPE_DOC,
        "v2_0_prd": _PRD_DOC,
    }

    for name in doctrine_loading_set:
        path = path_map.get(name)
        if not path:
            warnings.append(f"no path mapping for doctrine: {name}")
            continue
        if not path.exists():
            warnings.append(f"doctrine file not found: {path}")
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded[name] = f.read()
        except Exception as e:
            warnings.append(f"failed to load {name}: {e}")

    if warnings and not loaded:
        return {
            "doctrine_loaded": False,
            "errors": warnings,
            "loaded_at": datetime.now(timezone.utc).isoformat()
        }

    return {
        "doctrine_loaded": True,
        "doctrine_snapshot": loaded,
        "warnings": warnings if warnings else None,
        "loaded_at": datetime.now(timezone.utc).isoformat()
    }


def _load_nova_draft(artifact_path: str) -> tuple[bool, str, Optional[str]]:
    """Load Nova's Foundation draft from artifact_path."""
    if not artifact_path:
        return False, "", "artifact_path is empty"
    path = Path(artifact_path)
    if not path.exists():
        return False, "", f"draft file not found: {artifact_path}"
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return True, content, None
    except Exception as e:
        return False, "", f"failed to read draft: {e}"


def _extract_sections(text: str) -> Dict[str, str]:
    """
    Extract markdown sections from text.
    Returns {section_name: section_content}.
    """
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


def _section_matches_draft(section_name: str, draft_sections: Dict[str, str],
                           doctrine_sections: Dict[str, str]) -> Tuple[bool, str]:
    """
    Check if a draft section covers a doctrine section topic.
    Returns (matched: bool, notes: str).
    """
    draft_text = ' '.join(draft_sections.values()).lower()
    doctrine_keys = list(doctrine_sections.keys())
    matched = False
    notes = ""

    for key in doctrine_keys:
        if key.lower() in draft_text or any(
            kw in draft_text for kw in section_name.lower().split()
        ):
            matched = True
            notes = f"Found overlap with doctrine section: {key}"
            break

    if not matched:
        notes = f"No draft content matching doctrine section '{section_name}'"

    return matched, notes


def _produce_review_judgment(
    collab_id: str,
    draft_content: str,
    doctrine_snapshot: dict,
    review_scope: str
) -> Tuple[str, str]:
    """
    Doctrine-driven review judgment.

    Compares Nova's draft against three doctrine sources:
    - V2.0 Foundation baseline: vision, goals, principles
    - V2.0 Scope: what is in/out of scope
    - V2.0 PRD: functional requirements and acceptance criteria

    Produces section-by-section analysis and overall review_result.
    """
    baseline = doctrine_snapshot.get("v2_0_foundation_baseline", "")
    scope_doc = doctrine_snapshot.get("v2_0_scope", "")
    prd_doc = doctrine_snapshot.get("v2_0_prd", "")

    baseline_sections = _extract_sections(baseline)
    scope_sections = _extract_sections(scope_doc)
    prd_sections = _extract_sections(prd_doc)

    draft_sections = _extract_sections(draft_content)
    draft_len = len(draft_content) if draft_content else 0

    # ── Baseline alignment check ────────────────────────────────────────────────
    baseline_checks = []
    for bs_name, bs_content in baseline_sections.items():
        if len(bs_content) < 20:
            continue
        draft_lower = draft_content.lower()
        # Check if baseline section topic is referenced in draft
        keywords = [w for w in bs_name.lower().split() if len(w) > 3]
        matched = any(kw in draft_lower for kw in keywords) if keywords else False
        baseline_checks.append({
            "doctrine_section": bs_name,
            "present_in_draft": matched,
            "chars": len(bs_content)
        })

    baseline_covered = sum(1 for c in baseline_checks if c["present_in_draft"])
    baseline_total = len(baseline_checks)

    # ── Scope coverage check ────────────────────────────────────────────────────
    scope_checks = []
    for sc_name, sc_content in scope_sections.items():
        if len(sc_content) < 20:
            continue
        draft_lower = draft_content.lower()
        keywords = [w for w in sc_name.lower().split() if len(w) > 3]
        matched = any(kw in draft_lower for kw in keywords) if keywords else False
        scope_checks.append({
            "doctrine_section": sc_name,
            "covered_in_draft": matched,
            "chars": len(sc_content)
        })

    scope_covered = sum(1 for c in scope_checks if c["covered_in_draft"])
    scope_total = len(scope_checks)

    # ── PRD requirement coverage ─────────────────────────────────────────────────
    prd_checks = []
    for pr_name, pr_content in prd_sections.items():
        if len(pr_content) < 30:
            continue
        draft_lower = draft_content.lower()
        # Extract requirement-like phrases (short lines, bullet points)
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

    # ── Determine review_result ─────────────────────────────────────────────────
    # thresholds for doctrine-driven judgment
    baseline_ok = baseline_covered / baseline_total >= 0.6 if baseline_total else False
    scope_ok = scope_covered / scope_total >= 0.5 if scope_total else False
    prd_ok = prd_coverage_pct >= 40 if prd_total_requirements else False

    if baseline_ok and scope_ok and prd_ok:
        review_result = "approved"
    elif baseline_ok and (scope_ok or prd_ok):
        review_result = "revision_required"
    else:
        review_result = "blocked"

    # ── Build judgment report ───────────────────────────────────────────────────
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
        status = "✅" if c["present_in_draft"] else "❌"
        judgment += f"| {c['doctrine_section']} | {status} |\n"

    judgment += f"\n**Baseline coverage: {baseline_covered}/{baseline_total} ({baseline_covered/baseline_total*100:.0f}%)**\n\n"

    judgment += f"""## Scope Coverage ({scope_covered}/{scope_total} sections addressed)

| Doctrine Section | Addressed in Draft |
|------------------|-------------------|
"""
    for c in scope_checks:
        status = "✅" if c["covered_in_draft"] else "❌"
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
| Baseline alignment | ≥60% | {baseline_covered/baseline_total*100:.0f}% | {'✅' if baseline_ok else '❌'} |
| Scope coverage | ≥50% | {scope_covered/scope_total*100:.0f}% | {'✅' if scope_ok else '❌'} |
| PRD requirements | ≥40% | {prd_coverage_pct:.0f}% | {'✅' if prd_ok else '❌'} |

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

    judgment += "\n\n*Generated by Nexus Governed Execution Loop — Doctrine-driven review (Option B)*\n"

    return review_result, judgment


async def execute_review(handler: 'CollabHandler', collab_id: str, artifact_path: str,
                         review_scope: str, doctrine_loading_set: list):
    """
    Execute the Foundation review task (doctrine-driven Option B reviewer).

    Steps:
      1. Load doctrine (baseline + scope + PRD)
      2. Load Nova's draft
      3. Produce doctrine-driven review judgment
      4. Save judgment artifact
      5. Send review_response to Nova via NATS
      6. Update collab state
      7. Notify Alex via Telegram
    """
    handler._log("EXEC", f"[{collab_id}] starting doctrine-driven foundation_review")

    # 1. Load doctrine
    doctrine_result = _load_doctrine(doctrine_loading_set)
    if not doctrine_result.get("doctrine_loaded"):
        handler.store.update_collab(
            collab_id,
            status='in_progress',
            pending_action='awaiting_revision',
            last_event='doctrine_load_failed_review'
        )
        handler.store.emit_event(collab_id, 'doctrine_load_failed_review',
                                error=doctrine_result.get('errors'))
        handler._log("ERROR", f"[{collab_id}] doctrine_load_failed_review")
        return

    handler._log("EXEC", f"[{collab_id}] doctrine loaded OK: {list(doctrine_result.get('doctrine_snapshot', {}).keys())}")

    # 2. Load Nova's draft
    loaded, draft_content, error = _load_nova_draft(artifact_path)
    if not loaded:
        handler.store.update_collab(
            collab_id,
            status='in_progress',
            pending_action='awaiting_revision',
            last_event='draft_load_failed'
        )
        handler.store.emit_event(collab_id, 'draft_load_failed', error=error, artifact_path=artifact_path)
        handler._log("ERROR", f"[{collab_id}] draft_load_failed: {error}")
        return

    handler._log("EXEC", f"[{collab_id}] Nova draft loaded: {len(draft_content)} chars")

    # 3. Produce doctrine-driven review judgment
    review_result, judgment = _produce_review_judgment(
        collab_id,
        draft_content,
        doctrine_result.get("doctrine_snapshot", {}),
        review_scope
    )
    handler._log("EXEC", f"[{collab_id}] review judgment produced: {review_result}")

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

    # 5. Send review_response to Nova via NATS
    try:
        nc = getattr(handler, 'nc', None)
        if nc is None:
            raise RuntimeError("handler.nc is None")
        from governance.collab.notify import send_review_response_to_nova
        await send_review_response_to_nova(
            nc=nc,
            collab_id=collab_id,
            from_agent="jarvis",
            to_agent="nova",
            workflow="v2_0",
            stage="foundation_create_review",
            review_result=review_result,
            review_artifact_path=str(judgment_path) if judgment_path else "",
            review_notes=judgment[:500]
        )
        handler._log("EXEC", f"[{collab_id}] review_response sent to Nova")
    except Exception as e:
        handler._log("ERROR", f"[{collab_id}] failed to send review_response: {e}")

    # 6. Update collab state
    handler.store.update_collab(
        collab_id,
        status='completed',
        pending_action='',
        last_event='review_completed'
    )
    handler.store.emit_event(
        collab_id,
        'review_completed',
        review_result=review_result,
        review_judgment_path=str(judgment_path) if judgment_path else "",
        draft_chars=len(draft_content)
    )

    handler._log("EXEC", f"[{collab_id}] collab state updated: review_completed")

    # 7. Notify Alex via Telegram
    try:
        from governance.collab.notify import send_telegram_notification_async
        send_telegram_notification_async(
            f"*Foundation Review Complete*\n"
            f"Collab: `{collab_id}`\n"
            f"Draft: {len(draft_content)} chars\n"
            f"Result: *{review_result.upper()}*\n"
            f"Judgment: {str(judgment_path) if judgment_path else 'N/A'}"
        )
    except Exception as e:
        handler._log("WARN", f"[{collab_id}] Telegram notification failed: {e}")

    handler._log("EXEC", f"[{collab_id}] doctrine-driven foundation_review COMPLETE — result={review_result}")
