from __future__ import annotations

import asyncio
import json
import os
import time

import nats


NATS_URL = os.environ["NEXUS_RESIDENT_CONTROLLER_NATS_URL"]
RUN_ID = "wbs-7-19-14-5b-thunder-local"
AGENT_ID = "synthetic-local"
BASE = f"nexus.4_19.wbs7_19_14.{RUN_ID}.{AGENT_ID}"


async def main() -> None:
    nc = await nats.connect(servers=[NATS_URL], connect_timeout=5, max_reconnect_attempts=0)
    done = asyncio.Event()
    started = time.monotonic()

    async def publish(family: str, payload: dict) -> None:
        await nc.publish(f"{BASE}.{family}", json.dumps(payload, sort_keys=True).encode("utf-8"))
        await nc.flush()

    async def on_command(msg) -> None:
        subject = msg.subject
        if subject.endswith(".controller.init"):
            await publish("ack.controller_init", {"agent_id": AGENT_ID, "command": "controller_init"})
        elif subject.endswith(".assignment"):
            await publish("ack.assignment", {"assignment_id": "assign-5b-thunder-local"})
            await publish("progress.assignment", {"assignment_id": "assign-5b-thunder-local", "state": "synthetic_started"})
            await publish(
                "evidence.assignment",
                {"assignment_id": "assign-5b-thunder-local", "evidence_ref": "synthetic://5b/local"},
            )
            await publish(
                "result_candidate.assignment",
                {"assignment_id": "assign-5b-thunder-local", "candidate": "synthetic_non_business_success"},
            )
        elif subject.endswith(".drain"):
            await publish("offline.done", {"agent_id": AGENT_ID, "state": "offline"})
            done.set()

    await nc.subscribe(f"{BASE}.controller.init", cb=on_command)
    await nc.subscribe(f"{BASE}.assignment", cb=on_command)
    await nc.subscribe(f"{BASE}.drain", cb=on_command)
    await nc.flush()

    while not done.is_set() and time.monotonic() - started < 10:
        await publish("registration.ready", {"agent_id": AGENT_ID, "runtime_instance_id": "synthetic-runtime-5b"})
        await publish("readiness.ready", {"agent_id": AGENT_ID, "accepting_new_work": True})
        await publish("heartbeat.tick", {"agent_id": AGENT_ID, "state": "idle"})
        try:
            await asyncio.wait_for(done.wait(), timeout=0.25)
        except asyncio.TimeoutError:
            pass

    await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
