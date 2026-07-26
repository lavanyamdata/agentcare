import logging
from langgraph.graph import StateGraph, END
from app.orchestrator.state import AgentState
from app.agents.safety_agent import run_safety_agent
from app.agents.routing_agent import run_routing_agent
from app.agents.appointment_agent import run_appointment_agent
from app.agents.coordinator_agent import start_workflow, finalize_workflow
from app.services import escalation_service

logger = logging.getLogger("agentcare.orchestrator.graph")


def _route_after_safety(state: AgentState) -> str:
    return "routing" if state["is_safe"] else "finalize"


def _route_after_routing(state: AgentState) -> str:
    if state["department"] == "UNCLEAR":
        try:
            escalation_service.create_escalation(
                workflow_run_id=state["workflow_run_id"],
                reason="Routing could not determine a department",
                actor_id=state["user_id"],
            )
        except Exception as e:
            logger.error(f"UNCLEAR escalation failed: {e}")
            state["errors"].append(f"UNCLEAR escalation: {str(e)}")
        return "finalize"
    return "appointment"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("safety", run_safety_agent)
    g.add_node("routing", run_routing_agent)
    g.add_node("appointment", run_appointment_agent)
    g.add_node("finalize", finalize_workflow)

    g.set_entry_point("safety")
    g.add_conditional_edges("safety", _route_after_safety,
                            {"routing": "routing", "finalize": "finalize"})
    g.add_conditional_edges("routing", _route_after_routing,
                            {"appointment": "appointment", "finalize": "finalize"})
    g.add_edge("appointment", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_compiled = None

def run_agentcare_workflow(user_id: int, actor_role: str, user_message: str) -> AgentState:
    """Single entry point: UI calls this one function."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    state = start_workflow(user_id, actor_role, user_message)
    final_state = _compiled.invoke(state)
    return final_state
