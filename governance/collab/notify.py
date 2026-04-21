"""
Telegram notification helper for governed execution loop.
Sends proactive notifications to Alex via Telegram Bot HTTP API.
"""

import urllib.request
import urllib.error
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


_TELEGRAM_BOT_TOKEN = "8599695108:AAEFpu_ij3eSR4obBKfgfkrQejhnl2hkabQ"
_TELEGRAM_API_URL = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}"


def _send_telegram_sync(message: str, chat_id: str = "8231866924") -> bool:
    """
    Send a Telegram message via Bot HTTP API.
    Returns True if sent successfully, False otherwise.
    """
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
            else:
                print(f"[NOTIFY] Telegram API error: {result}")
                return False
    except urllib.error.HTTPError as e:
        print(f"[NOTIFY] HTTP error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"[NOTIFY] Telegram send failed: {e}")
        return False


def send_telegram_notification(message: str, chat_id: str = "8231866924") -> bool:
    """
    Send a Telegram notification.
    Called from daemon context (executor) when a "must notify" event occurs.
    """
    return _send_telegram_sync(message, chat_id)


def send_telegram_notification_async(message: str, chat_id: str = "8231866924"):
    """
    Fire-and-forget version: send Telegram notification without blocking.
    Runs in a background thread.
    """
    t = threading.Thread(target=_send_telegram_sync, args=(message, chat_id))
    t.start()
