import logging
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
