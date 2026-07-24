import logging
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
