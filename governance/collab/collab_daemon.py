"""
NATS Collaboration Daemon
Persistent background service: listener + worker loop + heartbeat + PID management
"""

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
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
_POLL_INTERVAL = 5    # seconds between worker polls
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


def _is_process_running(pid: int) -> bool:
    """Cross-platform process existence check."""
    if sys.platform.startswith('win'):
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}'],
            capture_output=True, text=True
        )
        return len(result.stdout.splitlines()) > 1
    else:
        # Unix: signal 0 — no actual signal sent, just checks existence
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _get_instance_id() -> str:
    """Return: hostname:pid:start_time (UTC epoch)."""
    return f"{socket.gethostname()}:{os.getpid()}:{int(datetime.now(timezone.utc).timestamp())}"


def _read_pid_metadata() -> dict:
    """Read structured PID metadata from PID file, or empty dict."""
    try:
        with open(_paths()['pid'], 'r', encoding='utf-8') as f:
            raw = f.read().strip()
        # Legacy format: raw PID number string — convert to structured metadata
        try:
            pid = int(raw)
            return {'pid': pid}
        except ValueError:
            # JSON format — parse as dict
            return json.loads(raw)
    except Exception:
        return {}



def _write_pid_metadata(metadata: dict):
    """Write structured PID metadata to PID file."""
    with open(_paths()['pid'], 'w', encoding='utf-8') as f:
        json.dump(metadata, f)


def _acquire_pid() -> bool:
    """
    Try to acquire PID file (singleton guard).
    Returns True if acquired, False if another instance is already running.
    Cross-platform: tasklist on Windows, kill(pid, 0) on Unix.
    """
    pid_path = _paths()['pid']
    if os.path.exists(pid_path):
        try:
            meta = _read_pid_metadata()
            old_pid = meta.get('pid')
            if old_pid is None:
                # Legacy format: raw PID number — recover
                old_pid = int(open(pid_path, 'r').read().strip())

            if _is_process_running(old_pid):
                _log("FATAL", f"Another daemon instance is running (pid={old_pid}). Exiting.")
                return False
            else:
                _log("WARN", f"Stale PID file found (pid={old_pid}). Removing.")
        except (ValueError, OSError, AttributeError):
            pass
        os.remove(pid_path)

    meta = {
        'pid': os.getpid(),
        'hostname': socket.gethostname(),
        'start_epoch': int(datetime.now(timezone.utc).timestamp()),
        'instance_id': _get_instance_id(),
    }
    _write_pid_metadata(meta)
    _log("INFO", f"PID file acquired: {os.getpid()}")
    return True


def _release_pid():
    """Remove PID file on shutdown."""
    try:
        os.remove(_paths()['pid'])
    except OSError:
        pass


def _stop_remote_daemon(pid: int) -> bool:
    """
    Platform-specific stop of a remote daemon process.
    Unix: SIGTERM — daemon handles signal, runs stop() cleanly.
    Windows: taskkill /F — force-kill; daemon's signal handler never runs.
    Returns True if process stopped, False otherwise.
    """
    if sys.platform.startswith('win'):
        subprocess.run(['taskkill', '/PID', str(pid), '/F'])
        return True
    else:
        os.kill(pid, signal.SIGTERM)
        return True


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
        """"Graceful shutdown."""
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

        finally:
            # Always release PID file — ensures clean state even if timeout fires
            _release_pid()

        # Unsubscribe from NATS
        if self.nc:
            await self.nc.close()
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

            # Log IN before any processing
            self.store.log_message(envelope.as_dict(), 'IN')

            # Ensure collab exists before writing daemon-owned fields
            self.store.get_or_create_collab(
                envelope.collab_id,
                opened_by=envelope.from_,
                artifact_type=getattr(envelope, 'artifact_type', None) or '',
                artifact_path=getattr(envelope, 'artifact_path', None) or '',
                receiver=envelope.to,
            )
            # Daemon-only bookkeeping fields — do NOT overwrite workflow state (last_event is set by handler)
            self.store.update_collab(envelope.collab_id,
                last_message_id=envelope.message_id,
                last_processed_by=self.instance_id,
            )
            # last_event must NOT be set here — handler.handle_inbound owns it

            self._log("INFO", f"  -> [EVENT_DRIVEN] {envelope.message_type} dispatched")

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
                last_processed_by=self.instance_id,
            )
            # Log ACK IN
            self.store.log_message(ack.as_dict(), 'IN')

            await self.handler.handle_ack(ack)

        except Exception as e:
            self._log("ERROR", f"ERROR processing ACK: {e}")

    # ── Worker Loop ───────────────────────────────────────────────────

    async def _worker_loop(self):
        """Recovery sweep loop — NOT primary message handler.
        
        Runs every POLL_INTERVAL seconds. Checks for deferred/stalled items
        that the event-driven listener left behind. Labeled [RECOVERY_SWEEP]
        in logs to distinguish from primary event path.
        """
        while self._running:
            try:
                await asyncio.sleep(_POLL_INTERVAL)
                await self._poll_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log("ERROR", f"Worker loop error: {e}")

    async def _poll_workers(self):
        """Worker loop: checks for collabs with pending_action and executes tasks.

        Option B: worker triggers executor (not a separate sub-agent).
        When pending_action is set, worker constructs task context and calls executor.
        Worker does NOT execute business logic itself — it triggers the defined execution path.
        """
        from governance.collab.foundation_executor import execute_foundation_delivery, get_task_context

        collabs = self.store.list_collabs(status=None)  # all collabs, filter by pending_action
        if not collabs:
            return

        for c in collabs:
            action = c.pending_action

            if action == 'awaiting_foundation_draft':
                # Model A (auto-continuation): Nova delivers draft by writing to artifact_path.
                # When artifact exists, auto-trigger review_request — no additional Nova message needed.
                artifact_path = getattr(c, 'artifact_path', None) or ''
                if artifact_path:
                    from pathlib import Path
                    p = Path(artifact_path)
                    if p.exists():
                        self._log("WORKER", f"[AUTO-TRIGGER] collab_id={c.collab_id} artifact found → sending review_request")
                        # Construct and dispatch review_request envelope
                        from governance.collab.envelope import CollabEnvelope
                        import uuid
                        review_envelope = CollabEnvelope(
                            message_id=f"msg-{uuid.uuid4().hex[:12]}",
                            collab_id=c.collab_id,
                            message_type="review_request",
                            from_="jarvis",
                            to="nova",
                            artifact_type=getattr(c, 'artifact_type', None) or 'foundation',
                            artifact_path=artifact_path,
                            payload={
                                "review_scope": "foundation completeness and governance alignment",
                                "workflow": getattr(c, 'workflow', None) or 'v2_0',
                                "stage": "foundation_create_review"
                            },
                            summary=f"Auto-triggered review_request for {c.collab_id}"
                        )
                        # Log OUT so the message history reflects the continuation
                        self.store.log_message(review_envelope.as_dict(), 'OUT')
                        # Dispatch via handler (same process, event-driven path)
                        await self.handler.handle_inbound(review_envelope)
                        self._log("WORKER", f"[AUTO-TRIGGER] collab_id={c.collab_id} review_request dispatched")
                    else:
                        self._log("WORKER", f"[WAIT] collab_id={c.collab_id} awaiting_foundation_draft — artifact not found at {artifact_path}")
                else:
                    self._log("WORKER", f"[WAIT] collab_id={c.collab_id} awaiting_foundation_draft — no artifact_path set yet")

            elif action == 'awaiting_review_execution':
                # Handler owns this — do not process in worker sweep
                # Only a recovery case if handler missed it (check last_processed_by)
                self._log("WORKER", f"[SKIP] collab_id={c.collab_id} pending_action={action} — handler owns review execution")

            elif action == 'awaiting_artifact':
                self._log("WORKER", f"[RECOVERY_SWEEP] collab_id={c.collab_id} still waiting for artifact")
            elif action == 'process_review':
                self._log("WORKER", f"[RECOVERY_SWEEP] collab_id={c.collab_id} -> process_review (worker sweep, not event-driven)")
            else:
                self._log("WORKER", f"[RECOVERY_SWEEP] collab_id={c.collab_id} pending_action={action} (no auto-action)")

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
                meta = _read_pid_metadata()
                old_pid = meta.get('pid')
                if old_pid is None:
                    old_pid = int(open(pid_path, 'r').read().strip())
                stopped = _stop_remote_daemon(old_pid)
                if stopped:
                    _log("INFO", f"Stop signal sent to pid={old_pid}")
                # On force-kill (Windows /F), the daemon's stop() never runs — clean up PID file here
                _release_pid()
                _log("INFO", "PID file cleaned up after stop")
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
