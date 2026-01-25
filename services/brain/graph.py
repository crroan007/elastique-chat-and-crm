from langgraph.graph import StateGraph, END
from services.brain.schemas import AgentState
from services.brain.safety_worker import safety_worker
from services.brain.supervisor import supervisor_worker
from services.brain.workers import clinical_worker, protocol_worker, crm_worker, general_worker

def check_safety(state: AgentState) -> str:
    """Conditional edge for safety check."""
    if state.get("next_node") == "END":
        return "END"
    return "supervisor"

def check_supervisor_route(state: AgentState) -> str:
    """Conditional edge for supervisor routing."""
    # Returns the node name stored in 'next_node' by supervisor
    return state.get("next_node", "general_worker")

# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("safety_worker", safety_worker)
workflow.add_node("supervisor", supervisor_worker)
workflow.add_node("clinical_worker", clinical_worker)
workflow.add_node("protocol_worker", protocol_worker)
workflow.add_node("crm_worker", crm_worker)
workflow.add_node("general_worker", general_worker)

# 3. Define Edges
# Entry point is Safety Worker
workflow.set_entry_point("safety_worker")

# Safety -> Supervisor (conditional)
workflow.add_conditional_edges(
    "safety_worker",
    check_safety,
    {
        "END": END,
        "supervisor": "supervisor"
    }
)

# Supervisor -> Workers (conditional)
workflow.add_conditional_edges(
    "supervisor",
    check_supervisor_route,
    {
        "clinical_worker": "clinical_worker",
        "protocol_worker": "protocol_worker",
        "crm_worker": "crm_worker",
        "general_worker": "general_worker",
        "END": END
    }
)

# Workers -> END (for now, single turn)
workflow.add_edge("clinical_worker", END)
workflow.add_edge("protocol_worker", END)
workflow.add_edge("crm_worker", END)
workflow.add_edge("general_worker", END)

# 4. Compile
brain_graph = workflow.compile()
