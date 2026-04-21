"""
Phase 2 Test Sender — simulates Nova sending a review_request to Jarvis.
Reads all values from local collab_config.json. No hardcoding.
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

    # Subscribe before publishing
    print(f"Subscribing to {subjects['ack']}...")
    await nc.subscribe(subjects['ack'], cb=handle_ack)
    await nc.flush()
    print("Subscription active. Now publishing command.\n")

    # Build envelope — all values from config
    collab_id = f"phase2-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    envelope = {
        "message_id": message_id,
        "collab_id": collab_id,
        "message_type": "review_request",
        "from": sender_id,
        "to": target_id,
        "artifact_type": "phase2_test",
        "artifact_path": str(Path(__file__).resolve()),
        "payload": {"test": True, "purpose": "phase2_ack_return_path"},
        "summary": f"Phase 2 test: from={sender_id} to={target_id}",
        "protocol_version": config.get("protocol_version", "0.2"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(f"Publishing: collab_id={collab_id} from={sender_id} to={target_id}")
    await nc.publish(subjects['command'], json.dumps(envelope).encode('utf-8'))
    await nc.flush()
    print("Published. Waiting for ACK...\n")

    try:
        await asyncio.wait_for(ack_event.wait(), timeout=10.0)
        print(f"\n[SUCCESS] ACK received within timeout")
        print(f"[SUCCESS] Total ACKs received: {len(acks_received)}")
        for a in acks_received:
            print(f"  -> ack_id={a.get('message_id')} status={a.get('status')} result={a.get('result')}")
    except asyncio.TimeoutError:
        print(f"\n[FAIL] No ACK received within 10 seconds")
        print(f"[FAIL] ACKs received before timeout: {len(acks_received)}")

    await nc.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())