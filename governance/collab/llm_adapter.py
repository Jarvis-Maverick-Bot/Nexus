"""
LLM Adapter — Model Access Abstraction Layer
V0.2 LLM Review Contract implementation.

Principle: this module never contains business logic.
review_executor.py calls llm_adapter.judge() — no httpx/urllib direct calls.
"""

import json
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any


# ── Auth Profiles ──────────────────────────────────────────────────────────────

def _load_auth_profile(api_key_profile: str) -> str:
    """
    Load API key from OpenClaw auth-profiles.json.
    Profile format: 'namespace:profile-name' e.g. 'minimax:global'
    """
    # OpenClaw auth-profiles.json locations (checked in order)
    candidates = [
        Path(os.environ.get('OPENCLAW_AUTH_PROFILES',
            Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json")),
        Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json",
    ]

    for path in candidates:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                profiles = json.load(f).get('profiles', {})
            if api_key_profile in profiles:
                entry = profiles[api_key_profile]
                if entry.get('type') == 'api_key':
                    return entry['key']

    raise ValueError(f"api_key_profile '{api_key_profile}' not found in any auth-profiles.json")


# ── Output Schema ─────────────────────────────────────────────────────────────

@dataclass
class LLMOutput:
    """
    Structured output from LLM judge call.
    V0.2 contract: verdict + reasons + required_changes + raw.
    """
    verdict: str                    # approved | revision_required | blocked | review_execution_error
    reasons: str                   # factual findings
    required_changes: str          # concrete actionable items (empty if APPROVED)
    raw: str                       # unparsed raw output


# ── MiniMax Provider ───────────────────────────────────────────────────────────

_MINIMAX_BASE_URL = "https://api.minimax.io/anthropic/v1/messages"
_MINIMAX_MODEL = "MiniMax-M2.7"


@dataclass
class MiniMaxAdapter:
    """
    MiniMax LLM provider adapter.
    Handles HTTP call, retry, timeout — no business logic.
    """
    api_key: str
    model: str = _MINIMAX_MODEL
    timeout_seconds: int = 60
    max_retries: int = 2

    def judge(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> LLMOutput:
        """
        Call MiniMax LLM with system + user prompts.
        Returns LLMOutput with parsed verdict/reasons/required_changes.
        On API error: returns LLMOutput with verdict=review_execution_error.
        """
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    _MINIMAX_BASE_URL,
                    data=payload,
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    result_data = json.loads(resp.read().decode("utf-8"))
                    content = result_data.get("content", [])
                    if isinstance(content, list) and len(content) > 0:
                        raw = content[0].get("text", "")
                    else:
                        raw = str(content)
                    return self._parse_output(raw, fallback_raw=raw)

            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    import time
                    time.sleep(1 * (attempt + 1))  # simple backoff

        # All retries exhausted
        return LLMOutput(
            verdict="review_execution_error",
            reasons=f"MiniMax API call failed after {self.max_retries + 1} attempts: {last_error}",
            required_changes="",
            raw=""
        )

    def _parse_output(self, raw: str, fallback_raw: str) -> LLMOutput:
        """
        Parse raw LLM output into three-field schema.
        V0.2 schema: VERDICT / REASONS / REQUIRED_CHANGES
        On parse failure: returns review_execution_error with raw preserved.
        """
        if not raw or not raw.strip():
            return LLMOutput(
                verdict="review_execution_error",
                reasons="parse failure: empty response from LLM",
                required_changes="",
                raw=fallback_raw
            )

        sections = self._find_sections(raw)

        verdict_raw = sections.get("VERDICT", "")
        reasons_raw = sections.get("REASONS", "")
        required_changes_raw = sections.get("REQUIRED_CHANGES", "")

        # Validate verdict
        allowed = {"APPROVED", "REVISION_REQUIRED", "BLOCKED"}
        verdict_normalized = verdict_raw.strip().upper() if verdict_raw else ""
        if verdict_normalized not in allowed:
            return LLMOutput(
                verdict="review_execution_error",
                reasons=f"VERDICT not in allowed set — received: '{verdict_raw}'. Raw output preserved.",
                required_changes="",
                raw=fallback_raw
            )

        # reasons must be non-empty for non-APPROVED
        if verdict_normalized != "APPROVED":
            if not reasons_raw or len(reasons_raw.strip()) < 10:
                return LLMOutput(
                    verdict="review_execution_error",
                    reasons=f"REASONS field empty or too short for verdict={verdict_normalized}. Raw output preserved.",
                    required_changes="",
                    raw=fallback_raw
                )

        return LLMOutput(
            verdict=verdict_normalized.lower(),  # approved | revision_required | blocked
            reasons=reasons_raw.strip(),
            required_changes=required_changes_raw.strip() if required_changes_raw else "",
            raw=fallback_raw
        )

    def _find_sections(self, raw: str) -> Dict[str, str]:
        """
        Find all sections in LLM output by section headers.
        Handles multi-line content within each section.
        Returns dict mapping section name (upper) to section content.
        """
        section_markers = ["VERDICT", "REASONS", "REQUIRED_CHANGES"]
        lines = raw.strip().split("\n")
        sections = {}
        current_section = None
        current_lines = []

        for line in lines:
            upper_stripped = line.strip().upper()
            is_header = any(upper_stripped.startswith(marker + ":") for marker in section_markers)

            if is_header:
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_lines)
                # Start new section
                current_section = next(m for m in section_markers if upper_stripped.startswith(m + ":"))
                current_lines = [line.split(":", 1)[1].strip()]
            elif current_section:
                current_lines.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_lines)

        return sections


# ── Adapter Factory ────────────────────────────────────────────────────────────

def create_llm_adapter(
    provider: str,
    api_key_profile: str,
    model: Optional[str] = None,
    timeout_seconds: int = 60,
    max_retries: int = 2
) -> MiniMaxAdapter:
    """
    Factory: create an LLM adapter from config.
    Currently supports MiniMax only. Extensible for OpenAI/Anthropic later.
    """
    if provider == "minimax":
        api_key = _load_auth_profile(api_key_profile)
        return MiniMaxAdapter(
            api_key=api_key,
            model=model or _MINIMAX_MODEL,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
