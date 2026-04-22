"""
Start V2.0 Foundation Create — test sender (TC1).

Command: "Start V2.0 Foundation Create"
Command intent: start_foundation_delivery
Workflow: v2_0 / stage: foundation_create

TC1 flow (updated — Nova-triggered via workflow_started):
1. Nova sends start_foundation_create to Jarvis (this test sends)
2. Jarvis daemon validates, creates collab, updates state
3. Jarvis returns ACK to Nova
4. Jarvis sends workflow_started to Nova
5. Nova receives workflow_started → triggers drafting continuation
   - execute_foundation_delivery (produce draft artifact)
   - send review_request to Jarvis
6. Jarvis receives review_request, executes review, returns review_response

This test script:
- Only sends start_foundation_create
- Observes ACKs received
- Observes workflow_started from Jarvis
- Does NOT manually open collab
- Does NOT manually run continuation
- Does NOT impersonate runtime
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

    # Collab_id for this run — used to filter observed messages
    collab_id = f"foundation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    ack_event = asyncio.Event()
    wf_started_event = asyncio.Event()
    review_request_event = asyncio.Event()

    async def handle_ack(msg):
        data = json.loads(msg.data.decode('utf-8'))
        if data.get('collab_id') != collab_id:
            return  # filter: ignore other collab traffic
        print(f"\n[ACK RECEIVED] message_id={data.get('message_id')} "
              f"ack_for={data.get('ack_for')} status={data.get('status')} "
              f"result={data.get('result')} to={data.get('to')} from={data.get('from')}")
        ack_event.set()

    async def handle_command(msg):
        data = json.loads(msg.data.decode('utf-8'))
        if data.get('collab_id') != collab_id:
            return  # filter: ignore other collab traffic
        msg_type = data.get('message_type', '')
        print(f"\n[CMD RECEIVED] message_type={msg_type} "
              f"from={data.get('from')} to={data.get('to')} collab_id={data.get('collab_id')}")
        if msg_type == 'workflow_started':
            print(f"[workflow_started] payload={data.get('payload', {})}")
            wf_started_event.set()
        elif msg_type == 'review_request':
            print(f"[review_request] artifact_path={data.get('artifact_path')} "
                  f"review_scope={data.get('payload', {}).get('review_scope')}")
            review_request_event.set()
        elif msg_type == 'review_response':
            print(f"[review_response] result={data.get('payload', {}).get('result')}")

    print(f"Subscribing to {subjects['ack']}...")
    await nc.subscribe(subjects['ack'], cb=handle_ack)
    await nc.subscribe(subjects['command'], cb=handle_command)
    await nc.flush()
    print("Subscription active. Now publishing start_foundation_create.\n")

    envelope = {
        "message_id": message_id,
        "collab_id": collab_id,
        "message_type": "start_foundation_create",
        "from": sender_id,
        "to": target_id,
        "artifact_type": "foundation",
        "artifact_path": "governance/docs/V2_0_FOUNDATION.md",
        "payload": {
            "command_intent": "start_foundation_delivery",
            "workflow": "v2_0",
            "stage": "foundation_create",
            "summary": "Start V2.0 Foundation Create"
        },
        "summary": f"Start V2.0 Foundation Create: {sender_id} -> {target_id}",
        "protocol_version": config.get("protocol_version", "0.2"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(f"Publishing: collab_id={collab_id} message_type=start_foundation_create "
          f"command_intent=start_foundation_delivery from={sender_id} to={target_id}")
    await nc.publish(subjects['command'], json.dumps(envelope).encode('utf-8'))
    await nc.flush()
    print("Published.\n")

    # Step 1: wait for ACK from Jarvis
    print("Step 1: Waiting for ACK from Jarvis...")
    try:
        await asyncio.wait_for(ack_event.wait(), timeout=10.0)
        print(f"[OK] ACK received\n")
    except asyncio.TimeoutError:
        print(f"[FAIL] No ACK within 10s\n")
        await nc.close()
        return

    # Step 2: wait for workflow_started from Jarvis
    print("Step 2: Waiting for workflow_started from Jarvis...")
    try:
        await asyncio.wait_for(wf_started_event.wait(), timeout=10.0)
        print(f"[OK] workflow_started received\n")
    except asyncio.TimeoutError:
        print(f"[FAIL] No workflow_started within 10s (Nova's continuation not triggered)\n")
        print(f"[INFO] collab_id={collab_id}")
        await nc.close()
        return

    # Step 3: wait for review_request from Nova (after drafting completes)
    print("Step 3: Waiting for review_request from Nova...")
    review_received = False
    try:
        await asyncio.wait_for(review_request_event.wait(), timeout=30.0)
        print(f"[OK] review_request received\n")
        review_received = True
    except asyncio.TimeoutError:
        print(f"[FAIL] No review_request within 30s after workflow_started\n")
        print(f"[INFO] collab_id={collab_id}")

    print(f"[TC1] collab_id={collab_id}")
    if review_received:
        print("[TC1] review_request observed — TC1 workflow progression confirmed")
    else:
        print("[TC1] review_request NOT observed — TC1 incomplete")

    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())