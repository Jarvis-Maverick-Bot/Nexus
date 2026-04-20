"""
NATS Collaboration Mechanism - Standing Listener
Subscribes to gov.collab.command and gov.collab.ack subjects
Processes messages through handler, emits ACKs, logs to durable store
"""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

# ── Resolve repo root for imports ─────────────────────────────────────
# listener.py is at: .../collab_module/listener.py
# Repo root is: .../collab_module/../  (2 levels up from collab_module/)
_REPO_ROOT = Path(__file__).parent.parent
_GOV_ROOT = str(_REPO_ROOT)
if _GOV_ROOT not in sys.path:
    sys.path.insert(0, _GOV_ROOT)

from nats import connect
from governance.collab.envelope import CollabEnvelope, AckEnvelope
from governance.collab.handler import SUBJECTS
from governance.collab.handler import CollabHandler
from governance.collab.state_store import CollabStateStore


# ── Configurable paths via environment variable ─────────────────────
_COLLAB_DATA_DIR = os.environ.get(
    "COLLAB_DATA_DIR",
    None  # default to computed relative path
)

if _COLLAB_DATA_DIR:
    _DATA_DIR = _COLLAB_DATA_DIR
else:
    _DATA_DIR = str(Path(__file__).parent.parent / "data")

STATE_FILE = os.path.join(_DATA_DIR, "collab_state.json")
LOG_FILE = os.path.join(_DATA_DIR, "collab_messages.jsonl")
MESSAGES_LOG = os.path.join(_DATA_DIR, "nats_collab_listener.log")
PID_FILE = os.path.join(_DATA_DIR, "nats_collab_listener.pid")


class StandingListener:
    """
    Long-running listener for NATS collaboration messages.
    Maintains durable state store. Emits ACKs automatically.
    """

    def __init__(self, my_id: str, nats_url: str = "nats://127.0.0.1:4222"):
        self.my_id = my_id
        self.nats_url = nats_url
        self.nc = None
        self.handler = None
        self.store = CollabStateStore(STATE_FILE, LOG_FILE)
        self._running = False
        self._sub_command = None
        self._sub_ack = None
        self._is_windows = sys.platform == 'win32' or os.name == 'nt'

        # Write PID — fixed: write current process PID to file
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except OSError as e:
            print(f"[WARNING] Could not write PID file {PID_FILE}: {e}")

    async def start(self):
        """Connect to NATS and subscribe."""
        self.nc = await connect(self.nats_url, max_reconnect_attempts=-1)
        self.handler = CollabHandler(self.nc, self.store, self.my_id)

        # Subscribe to command subject
        self._sub_command = await self.nc.subscribe(
            SUBJECTS['command'],
            cb=self._on_command
        )

        # Subscribe to ack subject
        self._sub_ack = await self.nc.subscribe(
            SUBJECTS['ack'],
            cb=self._on_ack
        )

        self._running = True
        self._log(f"Standing listener started. Subscribed to:")
        self._log(f"  {SUBJECTS['command']}")
        self._log(f"  {SUBJECTS['ack']}")
        self._log(f"My ID: {self.my_id}")
        self._log(f"State file: {STATE_FILE}")
        self._log(f"GOV_ROOT: {_GOV_ROOT}")

        # Keep alive
        await self._keep_alive()

    async def _on_command(self, msg):
        """Handle inbound command message."""
        try:
            envelope = CollabEnvelope.from_json(msg.data)
            self._log(f"CMD [{envelope.collab_id}] {envelope.message_type}: {envelope.summary}")

            success = await self.handler.handle_inbound(envelope)
            if success:
                self._log(f"  -> processed OK")
            else:
                self._log(f"  -> validation failed, discarded")

        except Exception as e:
            self._log(f"ERROR processing command: {e}")

    async def _on_ack(self, msg):
        """Handle inbound ACK message."""
        try:
            ack = AckEnvelope.from_json(msg.data)
            self._log(f"ACK [{ack.collab_id}] for={ack.ack_for} status={ack.status}")

            # Complete pending future if any
            await self.handler.handle_ack(ack)

        except Exception as e:
            self._log(f"ERROR processing ACK: {e}")

    async def _keep_alive(self):
        """Periodic alive log."""
        counter = 0
        while self._running:
            await asyncio.sleep(10)
            counter += 1
            collabs = self.store.list_collabs(status='in_progress')
            self._log(f"ALIVE {counter} - {len(collabs)} active collab(s)")

    def _log(self, line: str):
        """Log to file."""
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(hours=8))
        ts = datetime.now(tz).isoformat()
        msg = f"[{ts}] {line}"
        print(msg)
        try:
            with open(MESSAGES_LOG, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except OSError as e:
            print(f"[WARNING] Could not write to log {MESSAGES_LOG}: {e}")

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._sub_command:
            await self._sub_command.unsubscribe()
        if self._sub_ack:
            await self._sub_ack.unsubscribe()
        if self.nc:
            await self.nc.close()
        self._log("Listener stopped.")


async def main():
    my_id = sys.argv[1] if len(sys.argv) > 1 else "jarvis"
    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")

    listener = StandingListener(my_id=my_id, nats_url=nats_url)

    # Handle shutdown
    try:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(listener.stop()))
    except (NotImplementedError, OSError):
        pass  # Windows or no signal support

    try:
        await listener.start()
    except KeyboardInterrupt:
        await listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
