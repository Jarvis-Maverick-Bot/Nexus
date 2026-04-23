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
from typing import Optional, List, Dict, Any, Union


# ── Auth Profiles ──────────────────────────────────────────────────────────────

def _load_auth_profile(api_key_profile: str) -> dict:
    """
    Load auth entry from OpenClaw auth-profiles.json.
    Profile format: 'namespace:profile-name' e.g. 'minimax:global'
    Returns the full entry dict so callers can inspect type (api_key vs oauth).
    Raises ValueError if profile not found.
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
                return profiles[api_key_profile]

    raise ValueError(f"api_key_profile '{api_key_profile}' not found in any auth-profiles.json")


def _load_gateway_token() -> str:
    """
    Load the local OpenClaw gateway shared token.
    The OpenAI-compatible HTTP surface authenticates with gateway.auth.token,
    not with the upstream provider OAuth access token.
    """
    config_path = Path(os.environ.get('OPENCLAW_CONFIG_PATH', Path.home() / '.openclaw' / 'openclaw.json'))
    if not config_path.exists():
        raise ValueError(f"OpenClaw config not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    token = cfg.get('gateway', {}).get('auth', {}).get('token', '')
    if not token:
        raise ValueError('gateway.auth.token not found in OpenClaw config')
    return token


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

    def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Plain text generation call — returns (ok, text, error).
        Used by foundation_executor for draft generation.
        """
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
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
                        text = content[0].get("text", "")
                    else:
                        text = str(content)
                    if not text.strip():
                        return False, "", "llm_empty_output"
                    return True, text, None
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    import time
                    time.sleep(1 * (attempt + 1))

        return False, "", f"llm_generation_failed: {last_error}"


# ── OpenAI Provider ───────────────────────────────────────────────────────────

_OPENAI_BASE_URL = "http://localhost:18789/v1"  # OpenClaw gateway proxy
_OPENAI_GATEWAY_MODEL = "openclaw/main"


class OpenAIAdapter:
    """
    OpenAI LLM provider adapter via the local OpenClaw gateway HTTP surface.
    This path authenticates with the gateway shared token and targets gateway
    model ids such as `openclaw/main` rather than raw upstream model ids.
    """
    def __init__(
        self,
        api_key: str,
        model: str = _OPENAI_GATEWAY_MODEL,
        timeout_seconds: int = 60,
        max_retries: int = 2
    ):
        self.api_key = api_key
        self.model = model if model and model.startswith('openclaw') else _OPENAI_GATEWAY_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _call(self, payload: dict) -> dict:
        """Make HTTP call via urllib, with retries."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    f"{_OPENAI_BASE_URL}/chat/completions",
                    data=data,
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    import time; time.sleep(1 * (attempt + 1))
        raise RuntimeError(f"OpenAI API failed after {self.max_retries + 1} attempts: {last_error}")

    def _call_responses(self, payload: dict) -> dict:
        """Call OpenAI Responses API (newer endpoint)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    f"{_OPENAI_BASE_URL}/responses",
                    data=data,
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    import time; time.sleep(1 * (attempt + 1))
        raise RuntimeError(f"OpenAI Responses API failed after {self.max_retries + 1} attempts: {last_error}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Plain text generation call — returns (ok, text, error).
        Use Chat Completions as the primary path because that is the confirmed
        enabled gateway HTTP surface on Nova's machine.
        """
        try:
            return self._generate_via_chat(system_prompt, user_prompt)
        except Exception as e:
            return False, "", f"openai_generation_failed: {e}"

    def _generate_via_chat(self, system_prompt: str, user_prompt: str) -> tuple[bool, str, Optional[str]]:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        result = self._call(payload)
        choices = result.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")
            if text.strip():
                return True, text, None
        return False, "", "openai_empty_response"

    def judge(self, system_prompt: str, user_prompt: str) -> LLMOutput:
        """
        Structured judgment call via Chat Completions (V0.2 contract format).
        Returns LLMOutput with parsed verdict/reasons/required_changes.
        """
        _, text, err = self._generate_via_chat(system_prompt, user_prompt)
        if err:
            return LLMOutput(
                verdict="review_execution_error",
                reasons=f"OpenAI judge call failed: {err}",
                required_changes="",
                raw=""
            )
        return self._parse_judge_output(text, fallback_raw=text)

    def _parse_judge_output(self, raw: str, fallback_raw: str) -> LLMOutput:
        """Parse V0.2 three-line verdict from OpenAI response."""
        if not raw or not raw.strip():
            return LLMOutput(
                verdict="review_execution_error",
                reasons="parse failure: empty response",
                required_changes="",
                raw=fallback_raw
            )
        sections = self._find_sections(raw)
        verdict_raw = sections.get("VERDICT", "")
        reasons_raw = sections.get("REASONS", "")
        required_changes_raw = sections.get("REQUIRED_CHANGES", "")
        allowed = {"APPROVED", "REVISION_REQUIRED", "BLOCKED"}
        verdict_normalized = verdict_raw.strip().upper() if verdict_raw else ""
        if verdict_normalized not in allowed:
            return LLMOutput(
                verdict="review_execution_error",
                reasons=f"VERDICT not in allowed set — received: '{verdict_raw}'",
                required_changes="",
                raw=fallback_raw
            )
        if verdict_normalized != "APPROVED":
            if not reasons_raw or len(reasons_raw.strip()) < 10:
                return LLMOutput(
                    verdict="review_execution_error",
                    reasons=f"REASONS too short for verdict={verdict_normalized}",
                    required_changes="",
                    raw=fallback_raw
                )
        return LLMOutput(
            verdict=verdict_normalized.lower(),
            reasons=reasons_raw.strip(),
            required_changes=required_changes_raw.strip() if required_changes_raw else "",
            raw=fallback_raw
        )

    def _find_sections(self, raw: str) -> Dict[str, str]:
        section_markers = ["VERDICT", "REASONS", "REQUIRED_CHANGES"]
        lines = raw.strip().split("\n")
        sections = {}
        current_section = None
        current_lines = []
        for line in lines:
            upper_stripped = line.strip().upper()
            is_header = any(upper_stripped.startswith(m + ":") for m in section_markers)
            if is_header:
                if current_section:
                    sections[current_section] = "\n".join(current_lines)
                current_section = next(m for m in section_markers if upper_stripped.startswith(m + ":"))
                current_lines = [line.split(":", 1)[1].strip()]
            elif current_section:
                current_lines.append(line)
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
) -> Union[MiniMaxAdapter, OpenAIAdapter]:
    """
    Factory: create an LLM adapter from config.
    Supports 'minimax' and 'openai' (via OpenClaw gateway proxy).
    """
    if provider == "minimax":
        entry = _load_auth_profile(api_key_profile)
        api_key = entry.get("key") or ""
        return MiniMaxAdapter(
            api_key=api_key,
            model=model or _MINIMAX_MODEL,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries
        )
    elif provider in ("openai", "openai-codex"):
        # Validate that the requested local OpenClaw profile exists, but authenticate
        # to the gateway HTTP surface with the gateway shared token.
        _load_auth_profile(api_key_profile)
        gateway_token = _load_gateway_token()
        return OpenAIAdapter(
            api_key=gateway_token,
            model=model or _OPENAI_GATEWAY_MODEL,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
