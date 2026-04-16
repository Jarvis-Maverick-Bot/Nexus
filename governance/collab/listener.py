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

from nats import connect
from .envelope import CollabEnvelope, AckEnvelope
from .handler import SUBJECTS
from .handler import CollabHandler
from .state_store import CollabStateStore

# Paths relative to this file (collab/ subdir of governance/)
_REPO_ROOT = Path(__file__).parent.parent.parent
STATE_FILE = str(_REPO_ROOT / "governance" / "data" / "collab_state.json")
LOG_FILE = str(_REPO_ROOT / "governance" / "data" / "collab_messages.jsonl")
MESSAGES_LOG = str(_REPO_ROOT / "nats_collab_listener.log")
PID_FILE = str(_REPO_ROOT / "nats_collab_listener.pid")


class StandingListener:
    """
    Long-running listener for NATS collaboration messages.
    Maintains durable state store. Emits ACKs automatically.
    """
    
    def __init__(self, my_id: str, nats_url: str = None):
        self.my_id = my_id
        self.nats_url = nats_url or os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
        self.nc = None
        self.handler = None
        self.store = CollabStateStore(STATE_FILE, LOG_FILE)
        self._running = False
        self._sub_command = None
        self._sub_ack = None
        
        # Write PID
        with open(PID_FILE, 'w') as f:
            f.write(str(open(PID_FILE).read() if False else str(__import__('os').getpid())))
    
    async def start(self):
        import platform
        self._is_windows = platform.system() == 'Windows'
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
        import time
        counter = 0
        while self._running:
            await asyncio.sleep(10)
            counter += 1
            collabs = self.store.list_collabs(status='in_progress')
            self._log(f"ALIVE {counter} - {len(collabs)} active collab(s)")
    
    def _log(self, line: str):
        """Log to file."""
        ts = __import__('datetime').datetime.now(__import__('datetime').timezone(__import__('datetime').timedelta(hours=8))).isoformat()
        msg = f"[{ts}] {line}"
        print(msg)
        with open(MESSAGES_LOG, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    
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
    import sys
    my_id = sys.argv[1] if len(sys.argv) > 1 else "jarvis"
    
    listener = StandingListener(my_id=my_id)
    
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
