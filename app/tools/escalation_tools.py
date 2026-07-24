import logging
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
