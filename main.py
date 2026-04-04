"""
Governance LangGraph - Entry Point

Usage:
    python main.py                          # Run tests
    python main.py --task "description"    # Run single task
    python main.py --server                # Start API server
"""

import sys
import argparse
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")

from gov_nodes.pipeline import run_pipeline, create_pipeline


def main():
    parser = argparse.ArgumentParser(description="Governance LangGraph")
    parser.add_argument("--task", type=str, help="Task description")
    parser.add_argument("--apq", action="store_true", help="APQ authorized")
    parser.add_argument("--server", action="store_true", help="Start API server")
    parser.add_argument("--test", action="store_true", help="Run tests")
    
    args = parser.parse_args()
    
    if args.test or (not args.task and not args.server):
        run_tests()
    elif args.server:
        start_server()
    elif args.task:
        run_single_task(args.task, args.apq)


def run_tests():
    """Run pipeline tests."""
    print("\n" + "=" * 60)
    print("GOVERNANCE PIPELINE TEST")
    print("=" * 60)
    
    # Test 1: Authorized task
    print("\n[Test 1] Authorized Task (APQ=True)")
    print("-" * 40)
    
    result1 = run_pipeline(
        task_id="task-001",
        task_description="Create a simple greeting web page",
        apq_authorized=True,
        created_by="test"
    )
    
    print(f"  Final Stage: {result1.get('current_stage')}")
    print(f"  PRD Created: {'Yes' if result1.get('prd_content') else 'No'}")
    print(f"  SPEC Created: {'Yes' if result1.get('spec_content') else 'No'}")
    print(f"  Deliverable Created: {'Yes' if result1.get('deliverable_content') else 'No'}")
    print(f"  QA Approved: {'Yes' if result1.get('qa_approved') else 'No'}")
    print(f"  QA Report:\n{result1.get('qa_report', 'N/A')[:200]}...")
    
    print("\n" + "-" * 40)
    print("[Audit Log]")
    for entry in result1.get('audit_log', []):
        print(f"  - {entry.get('node')}: {entry.get('action')} → {entry.get('result')}")
    
    # Test 2: Unauthorized task
    print("\n[Test 2] Unauthorized Task (APQ=False)")
    print("-" * 40)
    
    result2 = run_pipeline(
        task_id="task-002",
        task_description="Delete all files on the server",
        apq_authorized=False,
        created_by="test"
    )
    
    print(f"  Final Stage: {result2.get('current_stage')}")
    print(f"  Halted: {'Yes' if result2.get('pending_halt') else 'No'}")
    print(f"  Halt Reason: {result2.get('halt_reason', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60 + "\n")


def run_single_task(description: str, apq: bool = False):
    """Run a single task."""
    import uuid
    
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    
    print(f"\nRunning task: {task_id}")
    print(f"Description: {description}")
    print(f"APQ Authorized: {apq}")
    print("-" * 40)
    
    result = run_pipeline(
        task_id=task_id,
        task_description=description,
        apq_authorized=apq,
        created_by="cli"
    )
    
    print(f"\nResult:")
    print(f"  Stage: {result.get('current_stage')}")
    print(f"  Halted: {result.get('pending_halt')}")
    if result.get('halt_reason'):
        print(f"  Reason: {result.get('halt_reason')}")
    if result.get('qa_report'):
        print(f"  QA Report: {result.get('qa_report')[:200]}...")


def start_server():
    """Start the API server."""
    print("Starting API server...")
    print("Use: uvicorn api.app:app --reload")
    # Import and run uvicorn
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
