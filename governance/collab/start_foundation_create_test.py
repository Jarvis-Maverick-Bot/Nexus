"""
Start V2.0 Foundation Create — test sender (TC1).

Command: "Start V2.0 Foundation Create"
Command intent: start_foundation_delivery
Workflow: v2_0 / stage: foundation_create

TC1 flow:
1. Nova opens collab (local state)
2. Nova sends start_foundation_create to Jarvis
3. Jarvis daemon validates, creates collab, updates state
4. Jarvis returns ACK to Nova
5. Nova TC1 continuation: execute foundation delivery + send review_request
6. Jarvis receives review_request, executes review, returns review_response
7. Nova receives review_response

Expected (after step 4):
- Jarvis state: status=open, pending_action=awaiting_foundation_draft

Expected (after step 5):
- Nova has produced Foundation artifact
- Nova has sent review_request to Jarvis
"""

import asyncio
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add repo root to path
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from nats import connect
from governance.collab.state_store import CollabStateStore
from governance.collab.envelope import CollabEnvelope


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
    print("Subscription active.\n")

    collab_id = f"foundation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    # Step 1: Open collab on Nova's side BEFORE sending
    # This ensures state exists when TC1 continuation triggers in handle_ack
    print(f"[TC1] Opening collab locally: {collab_id}")
    from governance.collab.state_store import STATE_FILE
    store = CollabStateStore(STATE_FILE)
    repo_root = Path(__file__).parent.parent.parent
    data_dir = repo_root / "governance" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    store.open_collab(
        collab_id=collab_id,
        opened_by=sender_id,
        receiver=target_id,
        artifact_type='foundation',
        artifact_path=str(repo_root / "governance" / "docs" / "V2_0_FOUNDATION.md")
    )
    store.update_collab(
        collab_id,
        status='in_progress',
        current_owner=sender_id,
        pending_action='',
        last_event='foundation_create_started'
    )
    print(f"[TC1] Collab opened locally. last_event=foundation_create_started, pending_action=''")

    # Step 2: Send start_foundation_create
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
    print("Published. Waiting for ACK...\n")

    # Step 3: Wait for ACK from Jarvis
    try:
        await asyncio.wait_for(ack_event.wait(), timeout=10.0)
        print(f"\n[ACK] Received within timeout. Total ACKs: {len(acks_received)}")
        for a in acks_received:
            print(f"  -> ack_id={a.get('message_id')} status={a.get('status')} "
                  f"result={a.get('result')} to={a.get('to')} from={a.get('from')}")
    except asyncio.TimeoutError:
        print(f"\n[FAIL] No ACK received within 10 seconds")
        await nc.close()
        return

    # Step 4: TC1 continuation — Nova executes foundation delivery + sends review_request
    # This runs after ACK is confirmed, as approved in the TC1 continuation spec.
    # Nova's CollabHandler.handle_ack triggers this in the real daemon.
    # In the test, we run it here in the test script context.
    print(f"\n[TC1 CONTINUATION] Starting foundation delivery...")
    from governance.collab.foundation_executor import execute_foundation_delivery
    from governance.collab.review_executor import _to_sharefolder_path

    task_context = {
        "collab_id": collab_id,
        "command_intent": "start_foundation_delivery",
        "doctrine_loading_set": ["v2_0_foundation_baseline", "v2_0_scope", "v2_0_prd"],
        "artifact_binding": {"output_path": "governance/docs/V2_0_FOUNDATION.md"},
        "payload": {}
    }

    # Create a minimal handler-like context for execute_foundation_delivery
    class _MinimalHandler:
        def __init__(self, nc, store, my_id):
            self.nc = nc
            self.store = store
            self.my_id = my_id
        def _log(self, tag, msg):
            print(f"  [{tag}] {msg}")

    handler_ctx = _MinimalHandler(nc, store, sender_id)
    await execute_foundation_delivery(handler_ctx, collab_id, task_context)
    print(f"[TC1 CONTINUATION] Foundation delivery complete.")

    # Get artifact path and convert to sharefolder UNC
    state = store.get_collab(collab_id)
    artifact_path = getattr(state, 'artifact_path', '') if state else ''
    artifact_path = _to_sharefolder_path(artifact_path)
    print(f"[TC1 CONTINUATION] Artifact path (UNC): {artifact_path}")

    # Send review_request to Jarvis
    review_message_id = f"msg-{uuid.uuid4().hex[:12]}"
    review_envelope = CollabEnvelope(
        message_id=review_message_id,
        collab_id=collab_id,
        message_type="review_request",
        from_=sender_id,
        to=target_id,
        artifact_type='foundation',
        artifact_path=artifact_path,
        payload={
            "review_scope": "foundation completeness and governance alignment",
            "workflow": "v2_0",
            "stage": "foundation_create_review"
        },
        summary=f"Foundation draft ready for review — {collab_id}"
    )
    store.log_message(review_envelope.as_dict(), 'OUT')
    await nc.publish(subjects['command'], review_envelope.to_json())
    await nc.flush()
    print(f"[TC1 CONTINUATION] review_request published (nova->jarvis)")

    print(f"\n[TC1 COMPLETE] Message flow delivered. Awaiting review_response from Jarvis.\n")
    print("Verify Nova state: python -c \"import json; print(json.dumps(json.load(open('D:\\\\Projects\\\\Nexus\\\\governance\\\\data\\\\collab_state.json')).get('" + collab_id + "', {}), indent=2))\"")

    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
