import logging
from typing import Dict, Any, List, Optional
from app.database.session import get_db
from app.database.models import Escalation, WorkflowRun
from app.services.audit_service import log_event

logger = logging.getLogger("agentcare.escalation")


def create_escalation(workflow_run_id, reason, actor_id=None):
    with get_db() as db:
        escalation = Escalation(
            workflow_run_id=workflow_run_id,
            reason=reason,
            status="pending",
        )
        db.add(escalation)
        run = db.query(WorkflowRun).filter_by(id=workflow_run_id).first()
        if run:
            run.status = "escalated"
            run.current_step = "escalation_review"
        db.flush()
        escalation_id = escalation.id
        logger.warning("Escalation created: id=" + str(escalation_id))
    log_event("ESCALATION_CREATED", actor_id=actor_id,
              entity_type="Escalation", entity_id=escalation_id,
              metadata={"workflow_run_id": workflow_run_id, "reason": reason})
    return {"escalation_id": escalation_id, "workflow_run_id": workflow_run_id,
            "reason": reason, "status": "pending"}


def resolve_escalation(escalation_id, decision, staff_notes, actor_role, actor_id):
    if actor_role != "staff":
        raise PermissionError("Only staff can resolve escalations.")
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision must be approved or rejected.")
    with get_db() as db:
        esc = db.query(Escalation).filter_by(id=escalation_id).first()
        if not esc:
            return {"success": False, "reason": "Escalation not found."}
        if esc.status != "pending":
            return {"success": False, "reason": "Already resolved: " + esc.status}
        esc.status = decision
        esc.reviewed_by = actor_id
        esc.staff_notes = staff_notes
        run = db.query(WorkflowRun).filter_by(id=esc.workflow_run_id).first()
        if run:
            run.status = "completed" if decision == "approved" else "failed"
        logger.info("Escalation " + str(escalation_id) + " resolved: " + decision)
    log_event("ESCALATION_" + decision.upper(), actor_id=actor_id,
              entity_type="Escalation", entity_id=escalation_id,
              metadata={"decision": decision, "notes": staff_notes})
    return {"success": True, "escalation_id": escalation_id, "decision": decision}


def get_pending_escalations(actor_role, actor_id):
    if actor_role != "staff":
        raise PermissionError("Only staff can view escalations.")
    with get_db() as db:
        escalations = (
            db.query(Escalation)
            .filter_by(status="pending")
            .order_by(Escalation.created_at.desc())
            .all()
        )
        return [
            {
                "escalation_id": e.id,
                "workflow_run_id": e.workflow_run_id,
                "reason": e.reason,
                "status": e.status,
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for e in escalations
        ]


def get_all_escalations(actor_role, actor_id):
    if actor_role != "staff":
        raise PermissionError("Only staff can view escalations.")
    with get_db() as db:
        escalations = (
            db.query(Escalation)
            .order_by(Escalation.created_at.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "escalation_id": e.id,
                "workflow_run_id": e.workflow_run_id,
                "reason": e.reason,
                "status": e.status,
                "reviewed_by": e.reviewed_by,
                "staff_notes": e.staff_notes,
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for e in escalations
        ]
