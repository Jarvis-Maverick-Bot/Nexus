"""
Foundation Review Executor — V0.2 LLM Review Contract
Rule layer + Evidence packer + LLM adapter call.

Principles:
- review_executor.py never imports urllib / httpx / boto3 directly
- llm_adapter.py owns all LLM provider interaction
- Rule layer fires before LLM call (fast-fail)
- Runtime validates output and rewrites if needed
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from governance.collab.runtime_contract_map import DomainResult
from governance.collab.llm_adapter import create_llm_adapter, LLMOutput


# ── Paths ─────────────────────────────────────────────────────────────────────

_SHARED_ROOT = Path(r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0")
_MACOS_SHAREFOLDER_BASE = "/Users/alex/Nova-Jarvis-Shared"
_SHAREFOLDER_BASE = r"\\192.168.31.124\Nova-Jarvis-Shared"

_FOUNDATION_BASELINE = _SHARED_ROOT / "01-release-definition" / "V2_0_FOUNDATION_V0_2.md"
_SCOPE_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_SCOPE_V0_2.md"
_PRD_DOC = _SHARED_ROOT / "01-release-definition" / "V2_0_PRD_V0_2.md"


# ── Cross-platform path ────────────────────────────────────────────────────────

def _to_sharefolder_path(artifact_path: str) -> str:
    """Convert macOS local path to Windows/Unix sharefolder path."""
    if not artifact_path:
        return artifact_path
    if artifact_path.startswith(_SHAREFOLDER_BASE.replace('\\\\', '\\')):
        return artifact_path
    if artifact_path.startswith(_MACOS_SHAREFOLDER_BASE):
        return artifact_path.replace(_MACOS_SHAREFOLDER_BASE, _SHAREFOLDER_BASE.replace('\\', '\\\\'))
    return artifact_path


# ── Config reader ─────────────────────────────────────────────────────────────

def _load_llm_config() -> dict:
    """Load LLM config from collab_config.json."""
    config_path = Path(__file__).parent / "collab_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("llm", {})
    return {}


# ── Rule Layer ────────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    """Result from rule layer — pass or fast-fail."""
    passed: bool          # True = LLM call needed; False = fast-fail
    verdict: str          # only meaningful when passed=False
    reasons: str
    required_changes: str
    rule_name: str        # which rule triggered the fast-fail


def _check_rule_draft_not_accessible(artifact_path: str) -> Optional[RuleResult]:
    """Rule: draft_not_accessible — artifact path is unreachable."""
    if not artifact_path:
        return RuleResult(
            passed=False,
            verdict="revision_required",
            reasons=f"artifact_path is empty — cannot locate draft",
            required_changes="Provide an accessible sharefolder path to the Foundation draft.",
            rule_name="draft_not_accessible"
        )
    sharefolder_path = _to_sharefolder_path(artifact_path)
    path = Path(sharefolder_path)
    if not path.exists():
        return RuleResult(
            passed=False,
            verdict="revision_required",
            reasons=f"Draft file not found at: {sharefolder_path}",
            required_changes="Provide an accessible sharefolder path to the Foundation draft.",
            rule_name="draft_not_accessible"
        )
    return None  # passed


def _check_rule_draft_empty(content: str) -> Optional[RuleResult]:
    """Rule: draft_empty — draft content is too short."""
    if content and len(content.strip()) < 50:
        return RuleResult(
            passed=False,
            verdict="blocked",
            reasons="Draft content is empty or too short (< 50 chars) — cannot review",
            required_changes="Submit a non-empty Foundation draft.",
            rule_name="draft_empty"
        )
    return None  # passed


def _check_rule_max_rounds_exceeded(review_round: int, max_review_rounds: int) -> Optional[RuleResult]:
    """Rule: max_rounds_exceeded — review_round > max_review_rounds."""
    if review_round > max_review_rounds:
        return RuleResult(
            passed=False,
            verdict="blocked",
            reasons=f"review_round ({review_round}) exceeds max_review_rounds ({max_review_rounds})",
            required_changes="",
            rule_name="max_rounds_exceeded"
        )
    return None  # passed


def _run_rule_layer(
    artifact_path: str,
    draft_content: str,
    review_round: int,
    max_review_rounds: int
) -> Optional[RuleResult]:
    """
    Run all rule-layer checks before LLM call.
    Returns None if all passed (LLM call needed).
    Returns RuleResult if any rule triggered fast-fail.
    """
    checks = [
        _check_rule_draft_not_accessible(artifact_path),
        _check_rule_draft_empty(draft_content),
        _check_rule_max_rounds_exceeded(review_round, max_review_rounds),
    ]
    for result in checks:
        if result is not None and not result.passed:
            return result
    return None  # all passed


# ── Evidence Packer ───────────────────────────────────────────────────────────

EVIDENCE_FULL_TEXT_MAX_CHARS = 8000  # default; overridden by config


def _load_doctrine_files(doctrine_loading_set: list) -> Dict[str, str]:
    """Load doctrine files. Returns {name: content}. Missing files logged as warnings."""
    loaded = {}
    path_map = {
        "v2_0_foundation_baseline": _FOUNDATION_BASELINE,
        "v2_0_scope": _SCOPE_DOC,
        "v2_0_prd": _PRD_DOC,
    }
    for name in doctrine_loading_set:
        path = path_map.get(name)
        if not path:
            continue
        if not path.exists():
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded[name] = f.read()
        except Exception:
            continue
    return loaded


def _pack_draft(draft_content: str, max_chars: int = EVIDENCE_FULL_TEXT_MAX_CHARS) -> str:
    """Pack draft: full text if short enough, else extractive summary."""
    if len(draft_content) <= max_chars:
        return draft_content
    # Extractive: first N chars + note that it was truncated
    return draft_content[:max_chars] + f"\n\n[... TRUNCATED — original length: {len(draft_content)} chars]"


def _pack_doctrine(doctrine_snapshot: Dict[str, str], max_chars: int = EVIDENCE_FULL_TEXT_MAX_CHARS) -> Dict[str, str]:
    """Pack each doctrine file: full if short, excerpted if long."""
    packed = {}
    for name, content in doctrine_snapshot.items():
        if len(content) <= max_chars:
            packed[name] = content
        else:
            packed[name] = content[:max_chars] + f"\n\n[... TRUNCATED — original length: {len(content)} chars]"
    return packed


def build_evidence_packet(
    draft_content: str,
    doctrine_snapshot: Dict[str, str],
    review_round: int,
    max_review_rounds: int,
    collab_id: str,
    is_final_round: bool,
    max_chars: int = EVIDENCE_FULL_TEXT_MAX_CHARS
) -> dict:
    """
    Build Layer B evidence packet per V0.2 contract.

    Decision authority: evidence_packer (rules engine, not hardcoded byte threshold).
    Threshold read from config: evidence_full_text_max_chars.
    """
    packed_doctrine = _pack_doctrine(doctrine_snapshot, max_chars)

    baseline = packed_doctrine.get("v2_0_foundation_baseline", "")
    scope = packed_doctrine.get("v2_0_scope", "")
    prd = packed_doctrine.get("v2_0_prd", "")

    review_context_parts = [
        f"Collab ID: {collab_id}",
        f"Review round: {review_round} of {max_review_rounds}",
    ]
    if is_final_round:
        review_context_parts.append("WARNING: This is the FINAL round. Max review rounds will be exhausted after this review.")
    review_context = "\n".join(review_context_parts)

    return {
        "draft_text": _pack_draft(draft_content, max_chars),
        "baseline_excerpt": baseline,
        "scope_excerpt": scope,
        "prd_excerpt": prd,
        "review_context": review_context
    }


# ── System Prompt Builder ─────────────────────────────────────────────────────

def _build_system_prompt(is_final_round: bool) -> str:
    """Build V0.2 system prompt for Foundation review judge."""
    final_round_note = (
        "\n\nIMPORTANT — FINAL ROUND WARNING:\n"
        "This is the FINAL review round. If you return REVISION_REQUIRED or BLOCKED, "
        "Nova will need to resubmit a revised draft. Be precise and actionable."
    ) if is_final_round else ""

    return f"""You are a strict V2.0 Foundation review judge. Your task is to review Nova's Foundation draft against the approved doctrine (Baseline, Scope, PRD) and return a precise judgment.

RULES:
- Output MUST be exactly three lines in the format:
  VERDICT: [APPROVED|REVISION_REQUIRED|BLOCKED]
  REASONS: [specific factual findings explaining your decision]
  REQUIRED_CHANGES: [concrete actionable items Nova must address — write 'NONE' if APPROVED]
- Never refuse to judge. Always produce a verdict.
- APPROVED: draft covers baseline meaningfully, addresses core scope, meets minimum PRD requirements
- REVISION_REQUIRED: draft covers baseline but has specific, actionable gaps
- BLOCKED: draft fails to adequately cover baseline sections or is fundamentally incomplete

Review Criteria:
- Baseline: draft must cover >= 60% of baseline sections meaningfully
- Scope: draft must address >= 50% of scope areas
- PRD: draft must cover >= 40% of PRD requirements

{final_round_note}"""


def _build_user_prompt(review_packet: dict, evidence_packet: dict) -> str:
    """Build user prompt for LLM."""
    return f"""Review the following Foundation draft for V2.0.

== NOVA'S FOUNDATION DRAFT TO REVIEW ==
{evidence_packet['draft_text']}

== FOUNDATION BASELINE (approved doctrine) ==
{evidence_packet['baseline_excerpt']}

== SCOPE (approved doctrine) ==
{evidence_packet['scope_excerpt']}

== PRD (approved doctrine) ==
{evidence_packet['prd_excerpt']}

== REVIEW CONTEXT ==
{evidence_packet['review_context']}

Respond with your judgment in the required three-line format:
VERDICT: [APPROVED|REVISION_REQUIRED|BLOCKED]
REASONS: [specific factual findings]
REQUIRED_CHANGES: [concrete actionable items — NONE if APPROVED]"""


# ── Doctrine Loading ───────────────────────────────────────────────────────────

def _load_nova_draft(artifact_path: str) -> Tuple[bool, str, Optional[str]]:
    """Load Nova's Foundation draft. Returns (loaded, content, error)."""
    if not artifact_path:
        return False, "", "artifact_path is empty"
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


def _load_doctrine(doctrine_loading_set: list) -> dict:
    """Load doctrine files. Returns doctrine_snapshot dict."""
    loaded = _load_doctrine_files(doctrine_loading_set)
    if not loaded:
        return {"doctrine_loaded": False, "errors": ["no doctrine files found"]}
    return {
        "doctrine_loaded": True,
        "doctrine_snapshot": loaded,
        "loaded_at": datetime.now(timezone.utc).isoformat()
    }


# ── Review Judgment Producer ──────────────────────────────────────────────────

def _produce_review_judgment(
    collab_id: str,
    draft_content: str,
    doctrine_snapshot: dict,
    review_round: int,
    max_review_rounds: int,
    is_final_round: bool,
    llm_config: dict
) -> LLMOutput:
    """
    Produce review judgment via LLM adapter.
    Returns LLMOutput with verdict/reasons/required_changes/raw.
    """
    evidence_packet = build_evidence_packet(
        draft_content=draft_content,
        doctrine_snapshot=doctrine_snapshot,
        review_round=review_round,
        max_review_rounds=max_review_rounds,
        collab_id=collab_id,
        is_final_round=is_final_round,
        max_chars=llm_config.get("evidence_full_text_max_chars", EVIDENCE_FULL_TEXT_MAX_CHARS)
    )

    system_prompt = _build_system_prompt(is_final_round)
    user_prompt = _build_user_prompt(
        review_packet={},
        evidence_packet=evidence_packet
    )

    adapter = create_llm_adapter(
        provider=llm_config.get("provider", "minimax"),
        api_key_profile=llm_config.get("api_key_profile", "minimax:global"),
        model=llm_config.get("model"),
        timeout_seconds=llm_config.get("timeout_seconds", 60),
        max_retries=llm_config.get("max_retries", 2)
    )

    return adapter.judge(system_prompt, user_prompt)


# ── Judgment Artifact Writer ──────────────────────────────────────────────────

def _write_judgment_artifact(
    collab_id: str,
    verdict: str,
    reasons: str,
    required_changes: str,
    review_round: int,
    max_review_rounds: int
) -> Optional[str]:
    """Write judgment artifact to governance/docs/ and shared drive."""
    import urllib.parse

    judgment_content = f"""# Foundation Review Judgment

**Collab ID:** {collab_id}
**Round:** {review_round} / {max_review_rounds}
**Result:** {verdict.upper()}
**Date:** {datetime.now(timezone.utc).isoformat()}
**Method:** V0.2 LLM Review Contract — MiniMax M2.7

---

## Verdict
{verdict.upper()}

## Reasons
{reasons}

## Required Changes
{required_changes if required_changes else 'NONE'}

---

*Generated by Nexus Governed Execution Loop — V0.2 LLM Review Contract*
"""

    repo_root = Path(__file__).parent.parent.parent
    local_path = repo_root / "governance" / "docs" / f"review_{collab_id}.md"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(judgment_content)
    except Exception:
        local_path = None

    # Shared drive primary path
    shared_path = _SHARED_ROOT / "reviews" / f"{collab_id}_review.md"
    try:
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        with open(shared_path, 'w', encoding='utf-8') as f:
            f.write(judgment_content)
    except Exception:
        pass  # Non-fatal — local cache still written

    return str(local_path) if local_path else None


# ── Main Executor ─────────────────────────────────────────────────────────────

async def execute_review(
    handler: 'CollabHandler',
    collab_id: str,
    artifact_path: str,
    review_scope: str,
    doctrine_loading_set: list
) -> DomainResult:
    """
    Execute V0.2 Foundation review task.

    Pipeline:
    1. Load doctrine
    2. Load Nova's draft
    3. Rule layer fast-fail checks (no LLM call)
    4. LLM call via adapter (if rules passed)
    5. Map LLMOutput → DomainResult
    6. Write judgment artifact
    7. Return DomainResult

    Does NOT: send NATS messages, update state, notify.
    Caller (CollabHandler pipeline) owns those.
    """
    handler._log("EXEC", f"[{collab_id}] starting V0.2 review_executor")

    # Load LLM config
    llm_config = _load_llm_config()
    max_review_rounds = llm_config.get("max_review_rounds", 3)

    # Get current review round from state
    state = handler.store.get_collab(collab_id)
    review_round = getattr(state, 'review_round', 0) or 0
    is_final_round = (review_round == max_review_rounds)

    # 1. Load doctrine
    doctrine_result = _load_doctrine(doctrine_loading_set)
    if not doctrine_result.get("doctrine_loaded"):
        handler._log("ERROR", f"[{collab_id}] doctrine_load_failed")
        return DomainResult(
            message_type='review_response',
            collab_id=collab_id,
            from_='jarvis',
            result='revision_required',
            notes=f"Review cannot proceed: doctrine files unavailable",
            reasons=f"Doctrine load failed for: {doctrine_loading_set}",
            required_changes="Ensure doctrine files are accessible at configured paths",
            workflow='v2_0',
            stage='foundation_create_review'
        )

    handler._log("EXEC", f"[{collab_id}] doctrine loaded: {list(doctrine_result['doctrine_snapshot'].keys())}")

    # 2. Load Nova's draft
    loaded, draft_content, error = _load_nova_draft(artifact_path)
    if not loaded:
        handler._log("ERROR", f"[{collab_id}] draft_load_failed: {error}")
        return DomainResult(
            message_type='review_response',
            collab_id=collab_id,
            from_='jarvis',
            result='revision_required',
            notes=f"Review cannot proceed: draft not found",
            reasons=f"Draft not accessible at: {artifact_path}",
            required_changes="Provide an accessible sharefolder path to the Foundation draft.",
            workflow='v2_0',
            stage='foundation_create_review'
        )

    handler._log("EXEC", f"[{collab_id}] draft loaded: {len(draft_content)} chars")

    # 3. Rule layer — fast-fail before LLM call
    rule_result = _run_rule_layer(
        artifact_path=artifact_path,
        draft_content=draft_content,
        review_round=review_round,
        max_review_rounds=max_review_rounds
    )

    if rule_result is not None:
        # Fast-fail: rule triggered, no LLM call
        handler._log("EXEC", f"[{collab_id}] rule_layer fast-fail: {rule_result.rule_name} -> verdict={rule_result.verdict}")

        # If max_rounds_exceeded, also update termination_reason in state
        if rule_result.rule_name == "max_rounds_exceeded":
            handler.store.update_collab(
                collab_id,
                status='blocked',
                pending_action='',
                termination_reason='max_review_rounds_exceeded'
            )

        judgment_path = _write_judgment_artifact(
            collab_id=collab_id,
            verdict=rule_result.verdict,
            reasons=rule_result.reasons,
            required_changes=rule_result.required_changes,
            review_round=review_round,
            max_review_rounds=max_review_rounds
        )

        return DomainResult(
            message_type='review_response',
            collab_id=collab_id,
            from_='jarvis',
            result=rule_result.verdict,
            notes=rule_result.reasons,  # backward compat
            reasons=rule_result.reasons,
            required_changes=rule_result.required_changes,
            judgment_path=judgment_path or '',
            workflow='v2_0',
            stage='foundation_create_review'
        )

    handler._log("EXEC", f"[{collab_id}] rule_layer passed — calling LLM")

    # 4. LLM call via adapter
    llm_output = _produce_review_judgment(
        collab_id=collab_id,
        draft_content=draft_content,
        doctrine_snapshot=doctrine_result["doctrine_snapshot"],
        review_round=review_round,
        max_review_rounds=max_review_rounds,
        is_final_round=is_final_round,
        llm_config=llm_config
    )

    handler._log("EXEC", f"[{collab_id}] LLM returned: verdict={llm_output.verdict}")

    # 5. Map LLMOutput → DomainResult
    judgment_path = _write_judgment_artifact(
        collab_id=collab_id,
        verdict=llm_output.verdict,
        reasons=llm_output.reasons,
        required_changes=llm_output.required_changes,
        review_round=review_round,
        max_review_rounds=max_review_rounds
    )

    handler._log("EXEC", f"[{collab_id}] review judgment written: {judgment_path}")
    handler._log("EXEC", f"[{collab_id}] V0.2 review_executor COMPLETE — result={llm_output.verdict}")

    return DomainResult(
        message_type='review_response',
        collab_id=collab_id,
        from_='jarvis',
        result=llm_output.verdict,          # approved | revision_required | blocked | review_execution_error
        notes=llm_output.reasons,           # backward compat
        reasons=llm_output.reasons,
        required_changes=llm_output.required_changes,
        judgment_path=judgment_path or '',
        workflow='v2_0',
        stage='foundation_create_review'
    )
