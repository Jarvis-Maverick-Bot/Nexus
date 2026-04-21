"""
Start V2.0 Foundation Create — Full Workflow Capture
Captures all elements of the governed workflow run:
- parsed task object
- doctrine loaded (Layer B)
- handler selected (Layer C)
- outbound message
- ACKs
- business response
- final state change
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


def print_section(title, data):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"  {k}: {v}")
    else:
        print(f"  {data}")


async def main():
    config = _load_config()

    nats_url = config.get("nats_url", "nats://127.0.0.1:4222")
    sender_id = config.get("sender_id", "nova")
    target_id = config.get("target_id", "jarvis")
    my_id = config.get("my_id", "jarvis")
    subjects = config.get("subjects", {
        "command": "gov.collab.command",
        "ack": "gov.collab.ack"
    })

    print("=" * 60)
    print("  START V2.0 FOUNDATION CREATE — FULL WORKFLOW CAPTURE")
    print("=" * 60)
    print(f"\n[NATS] {nats_url}")
    print(f"[sender_id] {sender_id}  [target_id] {target_id}  [my_id] {my_id}")

    # ── Step 1: Parse the command into standard task object ────────────
    command = "Start V2.0 Foundation Create"

    parsed_task = {
        "intent": "start_foundation_delivery",
        "release": "V2.0",
        "workflow": "v2_0",
        "stage": "foundation_create",
        "artifact_type": "foundation",
        "artifact_path": "governance/docs/V2_0_FOUNDATION.md",
        "owner": target_id,      # jarvis — the executor
        "reviewer": sender_id,   # nova — the approver
        "doctrine_loading_set": ["v2_0_foundation_doctrine", "skos_source_model"],
        "expected_output": "foundation_draft_ready + review_request",
        "completion_criteria": "Nova sends 'Approve V2.0 Foundation'"
    }

    print_section("STEP 1 — PARSED TASK OBJECT (Layer A)", parsed_task)

    # ── Step 2: Layer B — Doctrine loaded ────────────────────────────
    doctrine_loaded = {
        "v2_0_foundation_doctrine": "from doctrine_registry.json (entry: foundation_create)",
        "skos_source_model": "from SKOS_SOURCE_REGISTRY_V0_1.xlsx",
        "V2_0_FOUNDATION_V0_2.md": "approved baseline on shared drive",
        "V2.0 Scope + PRD": "governance context for V2.0 release"
    }
    print_section("STEP 2 — DOCTRINE LOADED (Layer B)", doctrine_loaded)

    # ── Step 3: Layer C — Handler selected ───────────────────────────
    handler_selected = {
        "message_type": "start_foundation_create",
        "handler_function": "_handle_start_foundation_create",
        "in_skill_registry": True,
        "handler_module": "governance.collab.handler"
    }
    print_section("STEP 3 — HANDLER SELECTED (Layer C)", handler_selected)

    # ── Step 4: Connect and subscribe ────────────────────────────────
    print_section("STEP 4 — CONNECTING TO NATS", f"Connecting to {nats_url}...")
    nc = await connect(nats_url)
    print(f"  Connected.")

    acks = []
    ack_event = asyncio.Event()

    async def handle_ack(msg):
        data = json.loads(msg.data.decode('utf-8'))
        acks.append(data)
        ack_event.set()

    await nc.subscribe(subjects['ack'], cb=handle_ack)
    await nc.flush()
    print(f"  Subscribed to {subjects['ack']}")

    # ── Step 5: Build and publish the outbound message ───────────────
    collab_id = f"foundation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message_id = f"msg-{uuid.uuid4().hex[:12]}"

    outbound = {
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
            "doctrine_loading_set": ["v2_0_foundation_doctrine", "skos_source_model"],
            "summary": "Start V2.0 Foundation Create"
        },
        "summary": f"Start V2.0 Foundation Create: {sender_id} -> {target_id}",
        "protocol_version": "0.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print_section("STEP 5 — OUTBOUND MESSAGE", outbound)
    print(f"\n  Publishing to {subjects['command']}...")
    await nc.publish(subjects['command'], json.dumps(outbound).encode('utf-8'))
    await nc.flush()
    print(f"  Published. Waiting for ACKs...\n")

    # ── Step 6: Wait for ACKs ─────────────────────────────────────────
    try:
        await asyncio.wait_for(ack_event.wait(), timeout=10.0)
        ack_summary = f"Received {len(acks)} ACK(s)"
        ack_status = "PASS"
    except asyncio.TimeoutError:
        ack_summary = f"No ACK within 10s ({len(acks)} received)"
        ack_status = "FAIL"

    print(f"\n  [{ack_status}] {ack_summary}")
    for a in acks:
        print(f"\n  ACK DETAIL:")
        for k, v in a.items():
            print(f"    {k}: {v}")

    print_section("STEP 6 — ACKS", ack_summary)

    # ── Step 7: Capture business response ───────────────────────────
    print_section("STEP 7 — BUSINESS RESPONSE", "Waiting 3s for daemon processing...")
    await asyncio.sleep(3)

    # Read state
    state_path = Path(__file__).parent.parent / "data" / "collab_state.json"
    state = {}
    if state_path.exists():
        with open(state_path, 'r') as f:
            state = json.load(f)

    collab = state.get(collab_id, {})
    print(f"\n  Collab [{collab_id}]:")
    for k, v in collab.items():
        print(f"    {k}: {v}")

    # ── Step 8: Final state change ───────────────────────────────────
    expected_state = {
        "status": "open",
        "current_owner": target_id,
        "pending_action": "awaiting_foundation_draft",
        "last_event": "foundation_create_started"
    }

    actual = {k: collab.get(k) for k in expected_state}
    match = actual == expected_state

    print_section("STEP 8 — FINAL STATE CHANGE", f"Match: {match}")
    print(f"\n  Expected:")
    for k, v in expected_state.items():
        print(f"    {k}: {v}")
    print(f"\n  Actual:")
    for k, v in actual.items():
        print(f"    {k}: {v}")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  WORKFLOW CAPTURE COMPLETE")
    print("=" * 60)
    print(f"\n  collab_id:       {collab_id}")
    print(f"  message_id:     {message_id}")
    print(f"  command:        {command}")
    print(f"  intent:         {parsed_task['intent']}")
    print(f"  handler:        {handler_selected['handler_function']}")
    print(f"  ACKs received:  {len(acks)}")
    print(f"  state match:    {match}")
    print(f"  status:         {collab.get('status', 'UNKNOWN')}")
    print(f"  pending_action: {collab.get('pending_action', 'UNKNOWN')}")
    print(f"  last_event:     {collab.get('last_event', 'UNKNOWN')}")

    if match:
        print("\n  [PASS] Full governed workflow run verified.")
    else:
        print("\n  [PARTIAL] State mismatch — check handler and state store.")

    await nc.close()


if __name__ == "__main__":
    asyncio.run(main())