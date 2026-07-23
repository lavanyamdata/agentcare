import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from app.database.session import get_db
from app.database.models import WorkflowRun

logger = logging.getLogger("agentcare.workflow")


def create_workflow_run(patient_profile_id, raw_request):
    with get_db() as db:
        run = WorkflowRun(
            patient_id=patient_profile_id,
            raw_request=raw_request,
            current_step="started",
            state=json.dumps({}),
            status="running",
        )
        db.add(run)
        db.flush()
        run_id = run.id
        logger.info("WorkflowRun created: id=" + str(run_id))
    return {"workflow_run_id": run_id, "status": "running"}


def update_workflow_state(workflow_run_id, current_step, state, status=None):
    with get_db() as db:
        run = db.query(WorkflowRun).filter_by(id=workflow_run_id).first()
        if not run:
            logger.error("WorkflowRun not found: id=" + str(workflow_run_id))
            return
        run.current_step = current_step
        run.state = json.dumps(state, default=str)
        if status:
            run.status = status
        run.updated_at = datetime.now(timezone.utc)
        logger.info("WorkflowRun updated: id=" + str(workflow_run_id) + " step=" + current_step)


def get_workflow_run(workflow_run_id):
    with get_db() as db:
        run = db.query(WorkflowRun).filter_by(id=workflow_run_id).first()
        if not run:
            return None
        return {
            "workflow_run_id": run.id,
            "patient_id": run.patient_id,
            "raw_request": run.raw_request,
            "current_step": run.current_step,
            "state": json.loads(run.state or "{}"),
            "status": run.status,
            "created_at": run.created_at.strftime("%Y-%m-%d %H:%M"),
        }


def get_all_workflow_runs(actor_role):
    if actor_role != "staff":
        raise PermissionError("Only staff can view all workflow runs.")
    with get_db() as db:
        runs = (
            db.query(WorkflowRun)
            .order_by(WorkflowRun.created_at.desc())
            .limit(100)
            .all()
        )
        return [
            {
                "workflow_run_id": r.id,
                "patient_id": r.patient_id,
                "raw_request": r.raw_request[:80],
                "current_step": r.current_step,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in runs
        ]
