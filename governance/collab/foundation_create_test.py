"""
Foundation Create Test — sends a foundation_create message from Nova to Jarvis.
Tests workflow_registry.json driven dispatch against the real collab_daemon.

Message contract (from workflow_registry.json):
  - message_type: foundation_create
  - command_intent: start_foundation_delivery
  - artifact_type: foundation
  - artifact_path: governance/docs/V2_0_FOUNDATION.md

Expected handler: _handle_foundation_create → status in_progress,
pending_action=awaiting_artifact, event=foundation_create_received.
"""

import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from nats import connect


def _load_config() -> dict:
    config_path = Path(__file__).parent / "collab_config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


async def main():
    config = _load_config()

    nats_url = config.get("nats_url", "nats://127.0.0.1:4222")
    sender_id = config.get("sender_id", "nova")
    target_id = config.get("target_id", "jarvis")
    subjects = config.get("subjects", {
        "command": "gov.collab.command",
        "ack": "gov.collab.ack"
    })

    print(f"Connecting to {nats_url}...")
    nc = await connect(nats_url)
    print("Connected.")

    acks_received = []
    ack_event = asyncio.Event()

    async def handle_ack(msg):
        data = json.loads(msg.data.decode('utf-8'))
        print(f"\n[ACK RECEIVED] message_id={data.get('message_id')} "
              f"ack_for={data.get('ack_for')} status={data.get('status')} "
              f"result={data.get('result')} to={data.get('to')} from={data.get('from')}")
        acks_received.append(data)
        ack_event.set()

    print(f"Subscribing to {subjects['ack']}...")
    await nc.subscribe(subjects['ack'], cb=handle_ack)
    await nc.flush()
    print("Subscription active. Now publishing foundation_create.\n")

    collab_id = f"foundation-create-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    # Full message contract per workflow_registry.json
    envelope = {
        "message_id": message_id,
        "collab_id": collab_id,
        "message_type": "foundation_create",
        "from": sender_id,
        "to": target_id,
        "artifact_type": "foundation",
        "artifact_path": "governance/docs/V2_0_FOUNDATION.md",
        "payload": {
            "command_intent": "start_foundation_delivery",
            "workflow": "v2_0",
            "stage": "foundation_create",
            "doctrine_loading_set": ["v2_0_foundation_doctrine", "skos_source_model"],
            "summary": "Begin V2.0 Foundation delivery workflow"
        },
        "summary": f"Foundation Create: {sender_id} -> {target_id}",
        "protocol_version": config.get("protocol_version", "0.2"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(f"Publishing: collab_id={collab_id} message_type=foundation_create "
          f"command_intent=start_foundation_delivery from={sender_id} to={target_id}")
    await nc.publish(subjects['command'], json.dumps(envelope).encode('utf-8'))
    await nc.flush()
    print("Published. Waiting for ACK...\n")

    try:
        await asyncio.wait_for(ack_event.wait(), timeout=10.0)
        print(f"\n[SUCCESS] ACK received within timeout")
        print(f"[SUCCESS] Total ACKs received: {len(acks_received)}")
        for a in acks_received:
            print(f"  -> ack_id={a.get('message_id')} status={a.get('status')} "
                  f"result={a.get('result')} to={a.get('to')} from={a.get('from')}")
    except asyncio.TimeoutError:
        print(f"\n[FAIL] No ACK received within 10 seconds")
        print(f"[FAIL] ACKs received before timeout: {len(acks_received)}")
        for a in acks_received:
            print(f"  -> ack_id={a.get('message_id')} status={a.get('status')} "
                  f"to={a.get('to')} from={a.get('from')}")

    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())