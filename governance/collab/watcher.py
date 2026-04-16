"""
Collab Watcher — Jarvis-side Local Monitor
Monitors authoritative files for mechanism failures and owner-side stalls.
Lightweight, does not perform business reasoning.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict

# ── Paths ────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent.parent
LISTENER_LOG = str(_REPO_ROOT / "nats_collab_listener.log")
STATE_FILE = str(_REPO_ROOT / "governance" / "data" / "collab_state.json")
MESSAGES_FILE = str(_REPO_ROOT / "governance" / "data" / "collab_messages.jsonl")
ALERT_LOG = str(_REPO_ROOT / "governance" / "data" / "watcher_alerts.jsonl")
PID_FILE = str(_REPO_ROOT / "watcher.pid")

# ── Thresholds ────────────────────────────────────────────────────
MECHANISM_TIMEOUT_SEC = 30
BUSINESS_STALL_SEC = 300   # 5 min
OWNER_STALL_SEC = 300      # 5 min
ALIVE_INTERVAL_SEC = 10

# ── State ─────────────────────────────────────────────────────────
@dataclass
class CollabSnapshot:
    collab_id: str
    status: str
    current_owner: str
    pending_action: str
    last_message_id: str
    last_event: str
    last_business_msg_at: Optional[str] = None
    last_protocol_event_at: Optional[str] = None
    last_alive_at: Optional[float] = None
    last_check: float = field(default_factory=time.time)
    mechanism_stalled_since: Optional[float] = None
    business_stalled_since: Optional[float] = None
    owner_stalled_since: Optional[float] = None


class Watcher:
    def __init__(self):
        self.collabs: Dict[str, CollabSnapshot] = {}
        self.listener_pid = self._read_pid()
        self.last_listener_alive_count: Dict[str, int] = {}  # log offset -> alive count
        self._last_log_offset = 0
        self._running = False

    def _read_pid(self) -> Optional[int]:
        try:
            return int(open(PID_FILE).read().strip())
        except:
            return None

    def _write_pid(self):
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

    def _log_alert(self, level: str, alert_type: str, collab_id: str, message: str):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "alert_type": alert_type,
            "collab_id": collab_id,
            "message": message
        }
        print(f"[WATCHER][{level}] {alert_type} | {collab_id} | {message}")
        with open(ALERT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _read_state(self) -> dict:
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _read_messages(self, collab_id: str) -> list:
        """Read last N messages for a collab from JSONL."""
        msgs = []
        try:
            with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if entry.get('collab_id') == collab_id:
                            msgs.append(entry)
                    except:
                        continue
        except:
            pass
        return msgs[-50:]  # last 50 messages per collab

    def _parse_listener_log(self) -> dict:
        """Parse listener log for alive counts and events since last offset."""
        events = []
        alive_counts = {}
        try:
            with open(LISTENER_LOG, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines[self._last_log_offset:]:
                ts = self._extract_timestamp(line)
                if 'ALIVE' in line:
                    # Parse ALIVE count
                    parts = line.split('ALIVE')
                    if len(parts) > 1:
                        count_part = parts[1].strip().split(' ')[0]
                        try:
                            alive_counts[ts] = int(count_part)
                        except:
                            pass
                elif 'CMD [' in line or 'ACK [' in line:
                    events.append({'timestamp': ts, 'line': line.strip()})
            self._last_log_offset = len(lines)
        except:
            pass
        return {'alive_counts': alive_counts, 'events': events}

    def _extract_timestamp(self, line: str) -> str:
        try:
            # Format: [2026-04-17T01:10:00.000000+08:00]
            return line.split('[')[1].split(']')[0]
        except:
            return ""

    def _parse_ts_to_epoch(self, ts: str) -> float:
        try:
            dt = datetime.fromisoformat(ts)
            return dt.timestamp()
        except:
            return 0.0

    def _get_last_business_message_time(self, msgs: list) -> Optional[float]:
        BUSINESS_TYPES = {
            'open', 'review_request', 'review_response', 'review_judgment',
            'revision_request', 'revision_update', 'acceptance_proposal',
            'acceptance_confirmation', 'complete', 'exit', 'blocker_notice',
            'decision_proposal', 'decision_response', 'diagnosis_request',
            'diagnosis_response', 'notify'
        }
        for msg in reversed(msgs):
            if msg.get('message_type') in BUSINESS_TYPES:
                ts = msg.get('timestamp', '')
                if ts:
                    return self._parse_ts_to_epoch(ts)
        return None

    def _check_duplicate_listeners(self) -> bool:
        """Check if multiple python listener processes are running."""
        count = 0
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process python | Measure-Object | Select-Object -ExpandProperty Count'],
                capture_output=True, text=True
            )
            count = int(result.stdout.strip())
        except:
            pass
        return count > 1

    def update_collab_state(self, collab_id: str, state: dict):
        now = time.time()
        if collab_id not in self.collabs:
            self.collabs[collab_id] = CollabSnapshot(
                collab_id=collab_id,
                status=state.get('status', 'unknown'),
                current_owner=state.get('current_owner', ''),
                pending_action=state.get('pending_action', ''),
                last_message_id=state.get('last_message_id', ''),
                last_event=state.get('last_event', ''),
            )
        snap = self.collabs[collab_id]
        snap.status = state.get('status', snap.status)
        snap.current_owner = state.get('current_owner', snap.current_owner)
        snap.pending_action = state.get('pending_action', snap.pending_action)
        snap.last_message_id = state.get('last_message_id', snap.last_message_id)
        snap.last_event = state.get('last_event', snap.last_event)

        # Read messages to get business message time
        msgs = self._read_messages(collab_id)
        snap.last_business_msg_at = self._get_last_business_message_time(msgs)

        # Check protocol event time (last event timestamp from log)
        snap.last_protocol_event_at = now  # reset on each check

        snap.last_check = now

    def run_cycle(self):
        """Run one monitoring cycle. Returns list of alerts."""
        alerts = []
        now = time.time()

        # 1. Check listener alive
        log_data = self._parse_listener_log()

        # 2. Check duplicate listeners
        if self._check_duplicate_listeners():
            alerts.append(('warning', 'duplicate_listener', 'system',
                           'Multiple python listener processes detected'))

        # 3. Check state file
        state_data = self._read_state()
        active_collabs = [k for k, v in state_data.items() if v.get('status') in ('open', 'in_progress')]

        for collab_id in active_collabs:
            self.update_collab_state(collab_id, state_data[collab_id])

        # 4. Check each active collab for stalls
        for collab_id, snap in self.collabs.items():
            if snap.status not in ('open', 'in_progress'):
                continue

            # Owner-side execution stall check
            if snap.current_owner == 'jarvis' and snap.pending_action:
                elapsed = now - (snap.last_business_msg_at or snap.last_check)
                if elapsed > OWNER_STALL_SEC:
                    alerts.append(('critical', 'owner_side_execution_stall', collab_id,
                                   f'Owner=jarvis pending_action={snap.pending_action} stalled {int(elapsed)}s'))

            # Business-layer stall check (any active collab with no new business messages)
            if snap.last_business_msg_at:
                elapsed = now - snap.last_business_msg_at
                if elapsed > BUSINESS_STALL_SEC:
                    alerts.append(('warning', 'business_stall', collab_id,
                                   f'No business message for {int(elapsed)}s, status={snap.status}'))

        # Emit alerts
        for level, alert_type, collab_id, message in alerts:
            self._log_alert(level, alert_type, collab_id, message)

        return alerts

    def start(self):
        self._running = True
        self._write_pid()
        print(f"[WATCHER] Started. PID={os.getpid()}")
        print(f"[WATCHER] Monitoring: {STATE_FILE}")
        print(f"[WATCHER] Thresholds: mechanism={MECHANISM_TIMEOUT_SEC}s, business/owner={BUSINESS_STALL_SEC}s")

        while self._running:
            try:
                self.run_cycle()
            except Exception as e:
                print(f"[WATCHER][ERROR] {e}")
            time.sleep(5)  # check every 5 seconds

    def stop(self):
        self._running = False
        print("[WATCHER] Stopped.")


if __name__ == "__main__":
    watcher = Watcher()
    try:
        watcher.start()
    except KeyboardInterrupt:
        watcher.stop()