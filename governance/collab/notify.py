"""
Telegram + NATS notification helpers for governed execution loop.
Sends proactive notifications to Alex via Telegram Bot HTTP API.
Sends workflow messages to Nova via NATS gov.collab.command subject.
"""

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _load_telegram_bot_token() -> str:
    """
    Load Telegram bot token from OpenClaw auth-profiles.json.
    Checks OPENCLAW_AUTH_PROFILES env var first, then default locations.
    Falls back to collab_config.json for backward compatibility only.
    """
    # Try auth-profiles.json first (primary store)
    candidates = [
        Path(os.environ.get('OPENCLAW_AUTH_PROFILES',
            Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json")),
        Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f).get('profiles', {})
                entry = profiles.get('telegram:bot', {})
                if entry.get('type') == 'api_key':
                    return entry['key']
            except Exception:
                pass

    # Fallback: load from collab_config.json for backward compatibility
    # (only if auth-profiles.json does not have telegram:bot)
    config_path = Path(__file__).parent.parent / "collab" / "collab_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('telegram_bot_token', '')
    except Exception:
        return ''



def _load_config() -> dict:
    """Load collab config from governance/collab/collab_config.json."""
    config_path = Path(__file__).parent.parent / "collab" / "collab_config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


_cfg = _load_config()
_TELEGRAM_BOT_TOKEN = _load_telegram_bot_token()
_TELEGRAM_API_URL = (
    f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}"
    if _TELEGRAM_BOT_TOKEN else None
)


def _send_telegram_sync(message: str, chat_id: str = "8231866924") -> bool:
    """Send a Telegram message via Bot HTTP API. Returns True on success."""
    if not _TELEGRAM_BOT_TOKEN:
        print("[NOTIFY] Telegram bot token not configured in collab_config.json")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_TELEGRAM_API_URL}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("ok"):
                print(f"[NOTIFY] Telegram sent OK: {message[:60]}...")
                return True
            print(f"[NOTIFY] Telegram API error: {result}")
            return False
    except Exception as e:
        print(f"[NOTIFY] Telegram send failed: {e}")
        return False


def send_telegram_notification(message: str, chat_id: str = "8231866924") -> bool:
    """Send a Telegram notification (blocking)."""
    return _send_telegram_sync(message, chat_id)


def send_telegram_notification_async(message: str, chat_id: str = "8231866924"):
    """Send a Telegram notification without blocking (background thread)."""
    t = threading.Thread(target=_send_telegram_sync, args=(message, chat_id))
    t.start()


# ── NATS outbound helpers ────────────────────────────────────────────────────────

async def send_review_response_to_nova(
    nc,
    collab_id: str,
    from_agent: str,
    to_agent: str,
    workflow: str,
    stage: str,
    review_result: str,
    review_artifact_path: str,
    review_notes: str,
    subject: str = "gov.collab.command"
) -> bool:
    """
    Send review_response from Jarvis back to Nova via NATS gov.collab.command.
    """
    payload = {
        "message_type": "review_response",
        "collab_id": collab_id,
        "from": from_agent,
        "to": to_agent,
        "summary": f"Foundation review completed: {review_result}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "workflow": workflow,
            "stage": stage,
            "review_result": review_result,
            "review_artifact_path": review_artifact_path,
            "review_notes": review_notes
        }
    }

    try:
        await nc.publish(subject, json.dumps(payload).encode("utf-8"))
        await nc.flush()
        print(f"[NOTIFY] review_response sent to {to_agent}: {review_result}")
        return True
    except Exception as e:
        print(f"[NOTIFY] review_response send failed: {e}")
        return False
