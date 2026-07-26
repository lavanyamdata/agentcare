import logging
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
