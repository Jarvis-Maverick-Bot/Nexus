import asyncio, json, time, sys
sys.path.insert(0, "D:/Projects/Nexus/governance")
from governance.collab.nats_client import NATSCollabClient

async def test_review_flow():
    client = NATSCollabClient(nats_url="nats://127.0.0.1:4222")
    await client.connect()
    print("Connected to NATS")

    collab_id = f"live-test-{int(time.time())}"
    print(f"Sending review_request with collab_id={collab_id}")

    artifact_path = r"\\192.168.31.124\Nova-Jarvis-Shared\working\01-projects\Nexus\V2.0\01-release-definition\V2_0_FOUNDATION_V0_2.md"

    msg = {
        "message_type": "review_request",
        "collab_id": collab_id,
        "from": "nova",
        "to": "jarvis",
        "payload": {
            "artifact_path": artifact_path,
            "review_scope": "foundation completeness and governance alignment",
            "artifact_type": "foundation",
            "workflow": "v2_0",
            "stage": "foundation_create_review"
        },
        "summary": f"Foundation review handover: nova -> jarvis ({collab_id})",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    # Send the review_request
    await client.send("gov.collab.command", msg)
    print(f"Sent review_request to gov.collab.command")

    # Wait for responses
    received = []
    async def handler(msg):
        received.append(msg)
        print(f"RCVD on {msg.subject}: {str(msg.data)[:200]}")

    await client.subscribe("gov.collab.command", handler=handler)
    await client.subscribe("gov.collab.ack", handler=handler)
    await client.subscribe("gov.collab.event", handler=handler)

    print("Waiting 30s for responses...")
    await asyncio.sleep(30)

    print(f"\nTotal messages received: {len(received)}")
    for r in received:
        print(f"  {r.subject}: {str(r.data)[:300]}")

    await client.close()
    return collab_id, received

if __name__ == "__main__":
    collab_id, msgs = asyncio.run(test_review_flow())
    print(f"\ncollab_id: {collab_id}")