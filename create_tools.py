import os

files = {}

# ── __init__.py ──────────────────────────────────────────────
files["app/tools/__init__.py"] = ""

# ── patient_tools.py ─────────────────────────────────────────
files["app/tools/patient_tools.py"] = '''import logging
from langchain_core.tools import tool
from app.services import patient_service

logger = logging.getLogger("agentcare.tools.patient")

@tool
def get_or_create_patient(user_id: int, name: str, email: str) -> dict:
    """Look up an existing patient profile by user_id, or create one if it does not exist.
    Returns patient_profile_id and basic info. Always call this first before booking or documents."""
    try:
        result = patient_service.get_or_create_patient(
            user_id=user_id, name=name, email=email
        )
        logger.info(f"get_or_create_patient: user_id={user_id}")
        return result
    except Exception as e:
        logger.error(f"get_or_create_patient error: {e}")
        return {"error": str(e)}
'''

# ── appointment_tools.py ──────────────────────────────────────
files["app/tools/appointment_tools.py"] = '''import logging
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
'''

# ── document_tools.py ─────────────────────────────────────────
files["app/tools/document_tools.py"] = '''import logging
from langchain_core.tools import tool
from app.services import document_service

logger = logging.getLogger("agentcare.tools.document")

@tool
def check_missing_documents(patient_profile_id: int, department_name: str) -> dict:
    """Check which required documents are missing for a patient before a department visit.
    Returns list of missing document types. Call after department is confirmed."""
    try:
        result = document_service.check_missing_documents(
            patient_id=patient_profile_id,
            department_name=department_name
        )
        logger.info(f"check_missing_documents: patient={patient_profile_id} dept={department_name}")
        return result
    except Exception as e:
        logger.error(f"check_missing_documents error: {e}")
        return {"error": str(e)}

@tool
def get_patient_documents(patient_profile_id: int) -> dict:
    """Retrieve all documents uploaded by a patient.
    Returns list of documents with document_type, file_path, document_date."""
    try:
        docs = document_service.get_patient_documents(patient_id=patient_profile_id)
        logger.info(f"get_patient_documents: patient={patient_profile_id}")
        return {"documents": docs}
    except Exception as e:
        logger.error(f"get_patient_documents error: {e}")
        return {"error": str(e)}
'''

# ── escalation_tools.py ───────────────────────────────────────
files["app/tools/escalation_tools.py"] = '''import logging
from langchain_core.tools import tool
from app.services import escalation_service

logger = logging.getLogger("agentcare.tools.escalation")

@tool
def create_escalation(workflow_run_id: int, reason: str) -> dict:
    """Escalate a patient request for human review. Use when the request contains
    emergency language, requests diagnosis or prescription, or cannot be safely handled
    by the agent. Returns escalation_id and status."""
    try:
        result = escalation_service.create_escalation(
            workflow_run_id=workflow_run_id,
            reason=reason
        )
        logger.info(f"create_escalation: workflow_run_id={workflow_run_id}")
        return result
    except Exception as e:
        logger.error(f"create_escalation error: {e}")
        return {"error": str(e)}
'''

# ── Write all files ───────────────────────────────────────────
for path, content in files.items():
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created: {path}")

print("\nDone.")