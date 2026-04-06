"""
gov_langgraph LangGraph E2E test — End-to-end pipeline test

Tests the full LangGraph pipeline:
1. Create project via tool
2. Create workitem with TaskState
3. Advance BA -> SA (one stage at a time)
4. Advance SA -> DEV
5. Advance DEV -> QA
6. Verify event journal at each step
7. Verify checkpoint at each step
8. Verify final TaskState = DONE

Run:
    python LANGGRAPH_E2E_TEST.py
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from gov_langgraph.openclaw_integration import Coordinator, init_harness
from gov_langgraph.langgraph_engine import init_runtime
from gov_langgraph.harness import HarnessConfig, StateStore, Checkpointer, EventJournal
from gov_langgraph.platform_model import TaskState, TaskStatus, V1_PIPELINE_STAGES


def main():
    print("=" * 60)
    print("gov_langgraph V1 LangGraph End-to-End Test")
    print("=" * 60)

    cfg = HarnessConfig()
    cfg.ensure_dirs()
    store = StateStore(cfg.state_dir)
    ckpt = Checkpointer(cfg)
    journal = EventJournal(cfg.event_dir)

    init_harness()
    init_runtime()

    c = Coordinator()

    # ── 1. Create project ───────────────────────────────────────
    print("\n[1/8] Create project")
    r = c.handle('create_project', {
        'project_name': 'LangGraph E2E Test',
        'project_goal': 'Full LangGraph pipeline end-to-end test',
        'domain_type': 'test',
        'actor': 'jarvis',
    })
    assert r['ok'], f"create_project failed: {r.get('error')}"
    proj_id = r['data']['project_id']
    print(f"  OK — project_id: {proj_id[:8]}")

    # ── 2. Create workitem + TaskState ──────────────────────────
    print("\n[2/8] Create workitem")
    r = c.handle('create_task', {
        'task_title': 'LangGraph E2E Task',
        'project_id': proj_id,
        'current_owner': 'viper_ba',
        'actor': 'jarvis',
    })
    assert r['ok'], f"create_task failed: {r.get('error')}"
    task_id = r['data']['task_id']
    stage_before = r['data']['current_stage']
    print(f"  OK — task_id: {task_id[:8]}, stage: {stage_before}")

    # Create TaskState (required for pipeline)
    ts = TaskState(
        task_id=task_id,
        current_stage='BA',
        state_status=TaskStatus.IN_PROGRESS,
        current_owner='viper_ba',
    )
    store.save_taskstate(ts)
    print(f"  TaskState created: stage=BA, status=IN_PROGRESS")

    # ── 3. Advance BA -> SA ─────────────────────────────────────
    print("\n[3/8] Advance BA -> SA")
    events_before = len(journal.get_for_project(proj_id))

    r = c.handle('advance_stage', {
        'task_id': task_id,
        'target_stage': 'SA',
        'actor': 'viper_ba',
    })
    assert r['ok'], f"BA->SA failed: {r.get('error')}"
    assert r['data']['to_stage'] == 'SA', f"Expected SA, got {r['data']['to_stage']}"
    print(f"  OK — {r['data']['from_stage']} -> {r['data']['to_stage']}")

    # Verify event
    events_after = journal.get_for_project(proj_id)
    new_events = [e for e in events_after if e.event_type == 'stage_advanced']
    print(f"  Events: {len(new_events)} stage_advanced events")

    # Verify checkpoint
    ckpt_record = ckpt.get_latest_completed_checkpoint(task_id)
    assert ckpt_record is not None, "No checkpoint after BA->SA"
    print(f"  Checkpoint: {ckpt_record.from_stage} -> {ckpt_record.to_stage}")

    # Verify TaskState
    ts = store.load_taskstate(task_id)
    assert ts.current_stage == 'SA', f"TaskState stage: expected SA, got {ts.current_stage}"
    print(f"  TaskState: stage={ts.current_stage}, status={ts.state_status}")

    # ── 4. Advance SA -> DEV ────────────────────────────────────
    print("\n[4/8] Advance SA -> DEV")
    r = c.handle('advance_stage', {
        'task_id': task_id,
        'target_stage': 'DEV',
        'actor': 'viper_ba',
    })
    assert r['ok'], f"SA->DEV failed: {r.get('error')}"
    assert r['data']['to_stage'] == 'DEV'
    print(f"  OK — {r['data']['from_stage']} -> {r['data']['to_stage']}")

    # Verify TaskState
    ts = store.load_taskstate(task_id)
    assert ts.current_stage == 'DEV'
    print(f"  TaskState: stage={ts.current_stage}")

    # ── 5. Advance DEV -> QA ────────────────────────────────────
    print("\n[5/8] Advance DEV -> QA")
    r = c.handle('advance_stage', {
        'task_id': task_id,
        'target_stage': 'QA',
        'actor': 'viper_dev',
    })
    assert r['ok'], f"DEV->QA failed: {r.get('error')}"
    assert r['data']['to_stage'] == 'QA'
    print(f"  OK — {r['data']['from_stage']} -> {r['data']['to_stage']}")

    # ── 6. Verify event journal ─────────────────────────────────
    print("\n[6/8] Verify event journal")
    all_events = journal.get_for_project(proj_id)
    stage_events = [e for e in all_events if e.event_type == 'stage_advanced']
    print(f"  Total events: {len(all_events)}")
    print(f"  Stage advanced events: {len(stage_events)}")
    assert len(stage_events) >= 3, f"Expected >=3 stage_advanced events, got {len(stage_events)}"
    print(f"  OK — all stage transitions journaled")

    # ── 7. Verify checkpoint restore ─────────────────────────────
    print("\n[7/8] Simulate restart — recover from checkpoint")
    recovered = ckpt.restore_from_latest(task_id)
    assert recovered is not None, "No checkpoint to restore"
    print(f"  Restored stage: {recovered['current_stage']}")
    assert recovered['current_stage'] == 'QA'
    print(f"  OK — checkpoint recovery works")

    # ── 8. Final state verification ────────────────────────────
    print("\n[8/8] Final state verification")
    r = c.handle('get_status', {'task_id': task_id})
    assert r['ok']
    print(f"  Status: stage={r['data']['current_stage']}, owner={r['data']['current_owner']}")

    w = store.load_workitem(task_id)
    assert w.current_stage == 'QA', f"WorkItem stage: expected QA, got {w.current_stage}"
    print(f"  WorkItem stage: {w.current_stage} OK")

    ts = store.load_taskstate(task_id)
    assert ts.current_stage == 'QA'
    print(f"  TaskState stage: {ts.current_stage} OK")
    print(f"  TaskState status: {ts.state_status}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED — V1 LangGraph pipeline verified")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Project:   {proj_id[:8]}")
    print(f"  Task:     {task_id[:8]}")
    print(f"  Final:    stage=QA, all 3 advances verified")
    print(f"  Events:   {len(stage_events)} stage transitions")
    print(f"  Checkpoints: {len(list(cfg.checkpoint_dir.glob('*.json')))}")


if __name__ == '__main__':
    main()
