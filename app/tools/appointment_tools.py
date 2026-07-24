import logging
from langchain_core.tools import tool
from app.services import appointment_service

logger = logging.getLogger("agentcare.tools.appointment")

@tool
def get_available_slots(department_id: int) -> dict:
    """Get open appointment slots for a department. Returns list of slots with
    slot_id, doctor_name, start_time, end_time. Call before booking."""
    try:
        slots = appointment_service.get_available_slots(department_id=department_id)
        logger.info(f"get_available_slots: department_id={department_id}")
        return {"slots": slots}
    except Exception as e:
        logger.error(f"get_available_slots error: {e}")
        return {"error": str(e)}

@tool
def book_appointment(
    patient_profile_id: int,
    slot_id: int,
    reason: str,
    actor_role: str,
    actor_id: int
) -> dict:
    """Book an appointment for a patient. Requires slot_id from get_available_slots.
    actor_role must be patient or staff. Returns appointment_id and confirmation."""
    try:
        result = appointment_service.book_appointment(
            patient_profile_id=patient_profile_id,
            slot_id=slot_id,
            reason=reason,
            actor_role=actor_role,
            actor_id=actor_id
        )
        logger.info(f"book_appointment: patient={patient_profile_id} slot={slot_id}")
        return result
    except Exception as e:
        logger.error(f"book_appointment error: {e}")
        return {"error": str(e)}

@tool
def cancel_appointment(
    appointment_id: int,
    actor_role: str,
    actor_id: int
) -> dict:
    """Cancel an existing appointment by appointment_id.
    actor_role must be patient or staff. Returns updated status."""
    try:
        result = appointment_service.cancel_appointment(
            appointment_id=appointment_id,
            actor_role=actor_role,
            actor_id=actor_id
        )
        logger.info(f"cancel_appointment: appointment_id={appointment_id}")
        return result
    except Exception as e:
        logger.error(f"cancel_appointment error: {e}")
        return {"error": str(e)}
