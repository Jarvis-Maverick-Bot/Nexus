"""
gateway_spawner — Spawn agents via OpenClaw gateway WebSocket API.

Alternative to sessions_spawn when the openclaw Python package is unavailable.
Connects directly to the OpenClaw gateway at ws://127:0.0.1:18789/gateway
and sends JSON-RPC messages over WebSocket.

Auth: HMAC-SHA256 nonce challenge (gateway sends challenge → client signs → responds).
"""

from __future__ import annotations

import asyncio
import json
import hmac
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Optional

import sys
import os

# Add websockets to requirements check
try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789/gateway")
GATEWAY_TOKEN = os.environ.get(
    "OPENCLAW_GATEWAY_TOKEN",
    # Default from openclaw.json
    "266f73749e2810f1402c04ca44f447cc7299972748ad4b47"
)


@dataclass
class SpawnResult:
    ok: bool
    session_key: str | None = None
    status: str = ""  # "spawned" | "failed" | "auth_failed" | "no_websockets"
    error: str | None = None


def _create_auth_response(token: str, challenge: str) -> dict[str, str]:
    """Create HMAC-SHA256 auth response for gateway nonce challenge."""
    mac = hmac.new(
        token.encode(),
        challenge.encode(),
        hashlib.sha256
    )
    return {
        "algo": "hmac-sha256",
        "nonce": mac.hexdigest()
    }


async def _ws_spawn(
    task: str,
    agent_id: str,
    runtime: str = "subagent",
    mode: str = "run",
) -> SpawnResult:
    """WebSocket-based agent spawn via OpenClaw gateway."""
    if websockets is None:
        return SpawnResult(
            ok=False,
            status="no_websockets",
            error="websockets library not installed: pip install websockets",
        )

    try:
        async with websockets.connect(GATEWAY_URL, ping_interval=None) as ws:
            # Receive challenge
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            challenge_msg = json.loads(raw)

            if challenge_msg.get("type") != "event" or "challenge" not in str(challenge_msg):
                # Try parsing as non-challenge
                pass

            payload = challenge_msg.get("payload", {})
            nonce = payload.get("nonce", "")

            if not nonce:
                # Try receiving another message
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                challenge_msg = json.loads(raw)
                payload = challenge_msg.get("payload", {})
                nonce = payload.get("nonce", "")

            # Send auth response
            auth_msg = {
                "type": "auth",
                "auth": _create_auth_response(GATEWAY_TOKEN, nonce),
                "token": GATEWAY_TOKEN,
            }
            await ws.send(json.dumps(auth_msg))

            # Wait for auth result
            auth_result = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_data = json.loads(auth_result)
            if auth_data.get("type") == "event" and auth_data.get("event", "").startswith("auth."):
                if "success" not in auth_data.get("event", ""):
                    return SpawnResult(ok=False, status="auth_failed", error=f"Auth failed: {auth_data}")

            # Send spawn request
            spawn_msg = {
                "type": "spawn",
                "task": task,
                "runtime": runtime,
                "agentId": agent_id,
                "mode": mode,
            }
            await ws.send(json.dumps(spawn_msg))

            # Wait for spawn result
            spawn_result = await asyncio.wait_for(ws.recv(), timeout=30)
            result_data = json.loads(spawn_result)

            session_key = result_data.get("sessionKey") or result_data.get("session_key")
            return SpawnResult(
                ok=True,
                session_key=session_key,
                status="spawned",
            )

    except asyncio.TimeoutError:
        return SpawnResult(ok=False, status="timeout", error="Gateway communication timed out")
    except Exception as e:
        return SpawnResult(ok=False, status="failed", error=str(e))


def gateway_spawn(task: str, agent_id: str, runtime: str = "subagent", mode: str = "run") -> SpawnResult:
    """
    Synchronous wrapper around WebSocket-based gateway spawn.
    Runs the async _ws_spawn in a new event loop.
    """
    try:
        return asyncio.run(_ws_spawn(task, agent_id, runtime, mode))
    except Exception as e:
        return SpawnResult(ok=False, status="failed", error=str(e))
