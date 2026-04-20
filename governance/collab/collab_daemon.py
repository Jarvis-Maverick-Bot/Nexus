"""
NATS Collaboration Daemon
Persistent background service: listener + worker loop + heartbeat + PID management
"""

import asyncio
import json
import os
import signal
import sys
import socket
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Resolve repo root for imports ─────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from nats import connect
from governance.collab.envelope import CollabEnvelope, AckEnvelope
from governance.collab.handler import SUBJECTS
from governance.collab.handler import CollabHandler
from governance.collab.state_store import CollabStateStore


# ── Paths (initialized lazily in main()) ──────────────────────────────
def _data_dir() -> str:
    d = _DATA_DIR or str(Path(__file__).parent.parent / "data")
    os.makedirs(d, exist_ok=True)
    return d

def _paths():
    d = _data_dir()
    return {
        'state': os.path.join(d, "collab_state.json"),
        'log': os.path.join(d, "collab_messages.jsonl"),
        'daemon_log': os.path.join(d, "nats_collab_daemon.log"),
        'pid': os.path.join(d, "collab_daemon.pid"),
    }

# ── Defaults (override via collab_config.json) ──────────────────────────
_POLL_INTERVAL = 30   # seconds between worker polls
_HEARTBEAT_INTERVAL = 60  # seconds between heartbeats
_SHUTDOWN_GRACE = 30  # seconds to finish current work before hard stop
_DATA_DIR = None  # defaults to <repo>/governance/data


def _log_to_file(msg_type: str, line: str, log_path: str):
    """Log to a specific file + stdout."""
    tz = timezone(timedelta(hours=8))
    ts = datetime.now(tz).isoformat()
    full = f"[{ts}] [{msg_type}] {line}"
    print(full)
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(full + '\n')
    except OSError:
        pass


def _log(msg_type: str, line: str):
    """Log to daemon log (uses default path)."""
    try:
        p = _paths()
        _log_to_file(msg_type, line, p['daemon_log'])
    except Exception:
        # Fallback: print only if path not ready yet
        tz = timezone(timedelta(hours=8))
        print(f"[{datetime.now(tz).isoformat()}] [{msg_type}] {line}")


def _load_config() -> dict:
    """Load all config from collab_config.json."""
    config_path = Path(__file__).parent / "collab_config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def _get_instance_id() -> str:
    """Return: hostname:pid:start_time."""
    return f"{socket.gethostname()}:{os.getpid()}:{int(datetime.now(timezone.utc).timestamp())}"


def _acquire_pid() -> bool:
    """
    Try to acquire PID file.
    Returns True if acquired, False if another instance is already running.
    """
    pid_path = _paths()['pid']
    if os.path.exists(pid_path):
        try:
            old_pid = int(open(pid_path, 'r').read().strip())
            # Check if process is actually running (Windows-compatible)
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {old_pid}'],
                capture_output=True, text=True
            )
            if len(result.stdout.splitlines()) > 1:
                _log("FATAL", f"Another daemon instance is running (pid={old_pid}). Exiting.")
                return False
            else:
                _log("WARN", f"Stale PID file found (pid={old_pid}). Removing.")
        except (ValueError, OSError, subprocess.SubprocessError):
            pass
        os.remove(pid_path)

    with open(pid_path, 'w') as f:
        f.write(str(os.getpid()))
    _log("INFO", f"PID file acquired: {os.getpid()}")
    return True


def _release_pid():
    """Remove PID file on shutdown."""
    try:
        os.remove(_paths()['pid'])
    except OSError:
        pass


class CollabDaemon:
    """
    Persistent daemon: NATS listener + worker loop + heartbeat.
    All tasks run concurrently. Never exits unless stopped.
    """

    def __init__(self, my_id: str, nats_url: str):
        self.my_id = my_id
        self.nats_url = nats_url
        self.instance_id = _get_instance_id()
        self.nc = None
        self.handler = None
        p = _paths()
        self.store = CollabStateStore(p['state'], p['log'])
        self._running = False
        self._tasks = []   # background tasks
        self._shutdown_event = asyncio.Event()

    # ── Logging ────────────────────────────────────────────────────────

    def _log(self, level: str, line: str):
        p = _paths()
        _log_to_file(level, f"[{self.my_id}] {line}", p['daemon_log'])

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        """Start all daemon tasks. Does not return until shutdown."""
        self._running = True
        self._log("INFO", f"DAEMON_STARTED instance={self.instance_id} nats={self.nats_url}")

        # Connect to NATS
        self.nc = await connect(
            self.nats_url,
            max_reconnect_attempts=-1,
            reconnect_time_wait=5
        )
        self._log("INFO", "NATS connected")

        self.handler = CollabHandler(self.nc, self.store, self.my_id)

        # Recover any in_progress items from previous run
        await self._recover()

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._listener_command()),
            asyncio.create_task(self._listener_ack()),
            asyncio.create_task(self._worker_loop()),
            asyncio.create_task(self._heartbeat_loop()),
        ]
        self._log("INFO", f"All tasks started. instance={self.instance_id}")

        # Wait until shutdown
        await self._shutdown_event.wait()
        self._log("INFO", "Shutdown event received.")

    async def stop(self):
        """Graceful shutdown."""
        self._log("INFO", "DAEMON_STOPPED initiated")
        self._running = False
        self._shutdown_event.set()

        # Wait for graceful shutdown period
        try:
            await asyncio.wait_for(self._wait_tasks(), timeout=_SHUTDOWN_GRACE)
        except asyncio.TimeoutError:
            self._log("WARN", "Graceful shutdown timeout — cancelling remaining tasks")
            for t in self._tasks:
                if not t.done():
                    t.cancel()

        # Unsubscribe from NATS
        if self.nc:
            await self.nc.close()
        _release_pid()
        self._log("INFO", "DAEMON_STOPPED completed")

    async def _wait_tasks(self):
        """Wait for all background tasks to finish."""
        for t in self._tasks:
            if not t.done():
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    # ── Recovery on Startup ────────────────────────────────────────────

    async def _recover(self):
        """Pick up any in_progress collabs from previous run."""
        collabs = self.store.list_collabs(status='in_progress')
        if not collabs:
            return
        self._log("INFO", f"RECOVERING {len(collabs)} in_progress collab(s)")
        for c in collabs:
            self._log("RECOVERY", f"collab_id={c.collab_id} pending_action={c.pending_action} owner={c.current_owner}")

    # ── NATS Listeners ────────────────────────────────────────────────

    async def _listener_command(self):
        """Permanent subscription to gov.collab.command."""
        while self._running:
            try:
                await self.nc.subscribe(
                    SUBJECTS['command'],
                    cb=self._on_command
                )
                self._log("INFO", f"Subscribed to {SUBJECTS['command']}")
                # Keepalive until shutdown
                await self._shutdown_event.wait()
                break
            except Exception as e:
                self._log("ERROR", f"NATS command subscription error: {e}, retrying in 5s")
                await asyncio.sleep(5)

    async def _listener_ack(self):
        """Permanent subscription to gov.collab.ack."""
        while self._running:
            try:
                await self.nc.subscribe(
                    SUBJECTS['ack'],
                    cb=self._on_ack
                )
                self._log("INFO", f"Subscribed to {SUBJECTS['ack']}")
                await self._shutdown_event.wait()
                break
            except Exception as e:
                self._log("ERROR", f"NATS ack subscription error: {e}, retrying in 5s")
                await asyncio.sleep(5)

    async def _on_command(self, msg):
        """Handle inbound command — event-driven."""
        try:
            envelope = CollabEnvelope.from_json(msg.data)

            if envelope.to != self.my_id:
                self._log("SKIP", f"CMD [{envelope.collab_id}] to={envelope.to} (not me)")
                return

            self._log("CMD", f"[{envelope.collab_id}] {envelope.message_type}: {envelope.summary}")

            # Update state: last_processed_by this instance
            self.store.update_collab(envelope.collab_id,
                last_message_id=envelope.message_id,
                last_event='event_acknowledged',
            )

            success = await self.handler.handle_inbound(envelope)
            self._log("INFO", f"  -> processed {'OK' if success else 'FAILED'}")

        except Exception as e:
            self._log("ERROR", f"ERROR processing command: {e}")

    async def _on_ack(self, msg):
        """Handle inbound ACK."""
        try:
            ack = AckEnvelope.from_json(msg.data)

            if ack.to != self.my_id:
                self._log("SKIP", f"ACK [{ack.collab_id}] to={ack.to} (not me)")
                return

            self._log("ACK", f"[{ack.collab_id}] for={ack.ack_for} status={ack.status}")

            self.store.update_collab(ack.collab_id,
                last_event='ack_received',
            )

            await self.handler.handle_ack(ack)

        except Exception as e:
            self._log("ERROR", f"ERROR processing ACK: {e}")

    # ── Worker Loop ───────────────────────────────────────────────────

    async def _worker_loop(self):
        """Poll for in_progress items every POLL_INTERVAL seconds."""
        while self._running:
            try:
                await asyncio.sleep(_POLL_INTERVAL)
                await self._poll_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log("ERROR", f"Worker loop error: {e}")

    async def _poll_workers(self):
        """Check in_progress items and dispatch any ready ones."""
        collabs = self.store.list_collabs(status='in_progress')
        if not collabs:
            return

        for c in collabs:
            action = c.pending_action

            if action == 'process_review':
                self._log("WORKER", f"collab_id={c.collab_id} -> process_review (Phase 2 will dispatch skill)")
            elif action == 'awaiting_artifact':
                self._log("WORKER", f"collab_id={c.collab_id} still waiting for artifact")
            else:
                self._log("WORKER", f"collab_id={c.collab_id} pending_action={action} (no auto-action)")

    # ── Heartbeat ─────────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Log alive status every HEARTBEAT_INTERVAL seconds."""
        counter = 0
        while self._running:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            counter += 1
            collabs = self.store.list_collabs(status='in_progress')
            self._log("ALIVE", f"#{counter} instance={self.instance_id} active={len(collabs)}")


# ── Entry Point ────────────────────────────────────────────────────────

def _handle_signal(sig, daemon: CollabDaemon):
    """Bridge signal → async stop."""
    asyncio.create_task(daemon.stop())


async def main():
    # Parse CLI
    my_id = sys.argv[1] if len(sys.argv) > 1 else None
    nats_url = sys.argv[2] if len(sys.argv) > 2 else None
    stop_mode = '--stop' in sys.argv

    config = _load_config()
    if my_id is None:
        my_id = config.get("my_id", "jarvis")
    if nats_url is None:
        nats_url = config.get("nats_url", "nats://127.0.0.1:4222")

    # Load configurable constants (CLI overrides config; config overrides defaults)
    global _POLL_INTERVAL, _HEARTBEAT_INTERVAL, _SHUTDOWN_GRACE, _DATA_DIR
    _POLL_INTERVAL = int(os.environ.get('COLLAB_POLL_INTERVAL', config.get('poll_interval', _POLL_INTERVAL)))
    _HEARTBEAT_INTERVAL = int(os.environ.get('COLLAB_HEARTBEAT_INTERVAL', config.get('heartbeat_interval', _HEARTBEAT_INTERVAL)))
    _SHUTDOWN_GRACE = int(os.environ.get('COLLAB_SHUTDOWN_GRACE', config.get('shutdown_grace', _SHUTDOWN_GRACE)))
    _DATA_DIR = config.get('data_dir', _DATA_DIR or str(Path(__file__).parent.parent / "data"))

    # Handle --stop mode
    if stop_mode:
        _log("INFO", f"Stop signal received for my_id={my_id}")
        pid_path = _paths()['pid']
        if os.path.exists(pid_path):
            try:
                old_pid = int(open(pid_path, 'r').read().strip())
                os.kill(old_pid, signal.SIGTERM)
                _log("INFO", f"Sent SIGTERM to pid={old_pid}")
            except OSError as e:
                _log("WARN", f"Could not signal process: {e}")
        else:
            _log("WARN", f"No PID file found for {my_id}")
        return

    # Acquire PID — refuse if already running
    if not _acquire_pid():
        sys.exit(1)

    daemon = CollabDaemon(my_id=my_id, nats_url=nats_url)

    # Bridge signals on Unix; on Windows handle SIGINT manually
    try:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s, daemon))
    except (NotImplementedError, OSError):
        # Windows: use console handler
        pass

    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.stop()
    except Exception as e:
        _log("FATAL", f"Unhandled exception: {e}")
        await daemon.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())
