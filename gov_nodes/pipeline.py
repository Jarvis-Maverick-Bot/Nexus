# Governance LangGraph Pipeline
from langgraph.graph import StateGraph, END
from datetime import datetime

from gov_nodes.state import GovernanceState
from gov_nodes.nodes.maverick import maverick_evaluate, maverick_route
from gov_nodes.nodes.viper_ba import viper_ba_execute
from gov_nodes.nodes.viper_sa import viper_sa_execute
from gov_nodes.nodes.viper_dev import viper_dev_execute
from gov_nodes.nodes.viper_qa import viper_qa_execute, viper_qa_route
from gov_nodes.nodes.nova import nova_audit
from gov_nodes.edges import route_after_maverick, route_after_qa, end_pipeline


def create_pipeline() -> StateGraph:
    """
    Create the governance pipeline graph.
    
    Flow:
    START -> maverick -> [authorized?] -> viper_ba -> viper_sa -> viper_dev -> viper_qa -> [approved?] -> nova -> END
              |                                     |
           halted                               halted
    """
    
    # Create graph
    graph = StateGraph(GovernanceState)
    
    # Add nodes
    graph.add_node("maverick", maverick_evaluate)
    graph.add_node("viper_ba", viper_ba_execute)
    graph.add_node("viper_sa", viper_sa_execute)
    graph.add_node("viper_dev", viper_dev_execute)
    graph.add_node("viper_qa", viper_qa_execute)
    graph.add_node("nova", nova_audit)
    graph.add_node("halted", lambda state: state)  # Placeholder for halted state
    
    # Add edges
    graph.set_entry_point("maverick")
    
    # Maverick routes based on authorization
    graph.add_conditional_edges(
        "maverick",
        route_after_maverick,
        {
            "viper_ba": "viper_ba",
            "halted": "halted"
        }
    )
    
    # BA -> SA -> DEV -> QA chain
    graph.add_edge("viper_ba", "viper_sa")
    graph.add_edge("viper_sa", "viper_dev")
    graph.add_edge("viper_dev", "viper_qa")
    
    # QA routes to Nova or halts
    graph.add_conditional_edges(
        "viper_qa",
        route_after_qa,
        {
            "nova": "nova",
            "halted": "halted"
        }
    )
    
    # Nova and halted both end
    graph.add_edge("nova", END)
    graph.add_edge("halted", END)
    
    return graph.compile()


def create_initial_state(
    task_id: str,
    task_description: str,
    apq_authorized: bool = False,
    created_by: str | None = None
) -> GovernanceState:
    """
    Create initial state for a new task.
    """
    return GovernanceState(
        task_id=task_id,
        task_description=task_description,
        current_stage="INTAKE",
        apq_authorized=apq_authorized,
        authorization_source=None,
        pending_halt=False,
        halt_reason=None,
        governance_violations=[],
        prd_content=None,
        spec_content=None,
        deliverable_content=None,
        qa_report=None,
        qa_approved=None,
        audit_log=[],
        nova_findings=[],
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        created_by=created_by
    )


def run_pipeline(
    task_id: str,
    task_description: str,
    apq_authorized: bool = False,
    created_by: str | None = None
) -> GovernanceState:
    """
    Run the governance pipeline.
    """
    graph = create_pipeline()
    
    initial_state = create_initial_state(
        task_id=task_id,
        task_description=task_description,
        apq_authorized=apq_authorized,
        created_by=created_by
    )
    
    result = graph.invoke(initial_state)
    return result


if __name__ == "__main__":
    # Test the pipeline
    print("Testing Governance Pipeline...")
    print("=" * 50)
    
    # Test 1: Authorized task
    result1 = run_pipeline(
        task_id="test-001",
        task_description="Create a simple web page",
        apq_authorized=True,
        created_by="test"
    )
    
    print(f"\nTest 1 - Authorized Task:")
    print(f"  Final Stage: {result1.get('current_stage')}")
    print(f"  PRD Created: {result1.get('prd_content') is not None}")
    print(f"  SPEC Created: {result1.get('spec_content') is not None}")
    print(f"  Deliverable Created: {result1.get('deliverable_content') is not None}")
    print(f"  QA Approved: {result1.get('qa_approved')}")
    
    # Test 2: Unauthorized task
    result2 = run_pipeline(
        task_id="test-002",
        task_description="Delete all files",
        apq_authorized=False,
        created_by="test"
    )
    
    print(f"\nTest 2 - Unauthorized Task:")
    print(f"  Final Stage: {result2.get('current_stage')}")
    print(f"  Halted: {result2.get('pending_halt')}")
    print(f"  Halt Reason: {result2.get('halt_reason')}")
    
    print("\n" + "=" * 50)
    print("Pipeline tests complete!")
