"""
E2E lifecycle test — PMO Web UI
Tests: create project → kickoff task → status check → gate load
"""
import urllib.request
import json

BASE = "http://127.0.0.1:8000"

def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except Exception as e:
        return {"error": str(e)}, -1

print("=== E2E Lifecycle Test ===\n")

# 1. Create project
print("1. Create project...")
proj, s = api("POST", "/projects", {"project_name": "E2E Test Project", "project_owner": "Jarvis", "project_status": "active", "project_goal": "E2E lifecycle verification"})
print(f"   status={s} ok={proj.get('ok')} project_id={proj.get('project_id', 'N/A')}")
if not proj.get("ok"):
    print(f"   FAILED: {proj}")
    exit(1)
pid = proj["project_id"]

# 2. Kickoff task
print("\n2. Kickoff task...")
task, s = api("POST", "/kickoff", {
    "title": "E2E Kickoff Test",
    "description": "Full lifecycle verification",
    "priority": 1,
    "actor": "Jarvis",
    "assignee": "viper_ba",
    "project_id": pid,
})
print(f"   status={s} ok={task.get('ok')} task_id={task.get('task_id', 'N/A')}")
if not task.get("ok"):
    print(f"   FAILED: {task}")
    exit(1)
tid = task["task_id"]

# 3. Get task status
print("\n3. Get task status...")
status, s = api("GET", f"/tasks/{pid}")
print(f"   status={s} ok={status.get('ok')} tasks_count={len(status.get('tasks', []))}")

# 4. Get gate info
print("\n4. Load gate panel...")
gate, s = api("GET", f"/gate/{tid}")
print(f"   status={s} ok={gate.get('ok')} gate_status={gate.get('gate_status', 'N/A')}")

# 5. List projects
print("\n5. List projects...")
projs, s = api("GET", "/projects")
print(f"   status={s} ok={projs.get('ok')} count={len(projs.get('projects', []))}")

print("\n=== ALL CHECKS PASSED ===")
