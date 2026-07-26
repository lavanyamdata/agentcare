coordinator = '''import logging
from app.orchestrator.state import AgentState
from app.services import patient_service, workflow_service, reminder_service

logger = logging.getLogger("agentcare.agents.coordinator")


def start_workflow(user_id: int, actor_role: str, user_message: str) -> AgentState:
    """Coordinator entry: resolve patient, create WorkflowRun, build initial state."""
    logger.info(f"Coordinator starting workflow for user_id={user_id}")

    patient = patient_service.get_or_create_patient(
        user_id=user_id, actor_role=actor_role, actor_id=user_id
    )
    patient_profile_id = patient["patient_profile_id"]

    wf = workflow_service.create_workflow_run(
        patient_profile_id=patient_profile_id,
        raw_request=user_message,
    )

    state: AgentState = {
        "user_id": user_id,
        "patient_profile_id": patient_profile_id,
        "actor_role": actor_role,
        "user_message": user_message,
        "workflow_run_id": wf["workflow_run_id"],
        "is_safe": True,
        "escalation_reason": "",
        "department": "",
        "department_id": 0,
        "slot_id": 0,
        "appointment_id": 0,
        "final_response": "",
        "errors": [],
    }
    logger.info(f"Coordinator created workflow_run_id={wf['workflow_run_id']}")
    return state


def finalize_workflow(state: AgentState) -> AgentState:
    """Coordinator exit: set final_response, reminders on success, close WorkflowRun."""
    if not state["is_safe"]:
        state["final_response"] = (
            "Your request needs attention from our staff and has been "
            "escalated for review. Someone will follow up with you shortly."
        )
        status = "escalated"

    elif state["department"] == "UNCLEAR":
        state["final_response"] = (
            "We could not confidently match your request to a department, "
            "so it has been sent to our staff for review."
        )
        status = "escalated"

    elif state["appointment_id"]:
        if not state["final_response"]:
            state["final_response"] = "Your appointment has been booked."
        try:
            reminder_service.create_appointment_reminder(
                patient_profile_id=state["patient_profile_id"],
                appointment_id=state["appointment_id"],
                actor_id=state["user_id"],
            )
            reminder_service.create_followup_task(
                patient_profile_id=state["patient_profile_id"],
                appointment_id=state["appointment_id"],
                actor_id=state["user_id"],
            )
        except Exception as e:
            logger.error(f"Reminder creation failed: {e}")
            state["errors"].append(f"Reminders: {str(e)}")
        status = "completed"

    else:
        if not state["final_response"]:
            state["final_response"] = (
                "We could not complete your booking. Our staff will review your request."
            )
        status = "failed"

    try:
        workflow_service.update_workflow_state(
            workflow_run_id=state["workflow_run_id"],
            current_step="done",
            state=state,
            status=status,
        )
    except Exception as e:
        logger.error(f"Final workflow update failed: {e}")

    logger.info(f"Coordinator finalized workflow_run_id={state['workflow_run_id']} status={status}")
    return state
'''

graph = '''import logging
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
'''

with open("app/agents/coordinator_agent.py", "w", encoding="utf-8") as f:
    f.write(coordinator)
with open("app/orchestrator/graph.py", "w", encoding="utf-8") as f:
    f.write(graph)
print("Created: app/agents/coordinator_agent.py")
print("Created: app/orchestrator/graph.py")