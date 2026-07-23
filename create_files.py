import os

# ── patient_service.py ────────────────────────────────────────────
patient = '''import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import make_transient
from app.database.session import get_db
from app.database.models import User, PatientProfile
from app.services.audit_service import log_event

logger = logging.getLogger("agentcare.patient")


def get_or_create_patient(user_id, actor_role, actor_id):
    if actor_role == "patient" and actor_id != user_id:
        raise PermissionError("Access denied.")
    with get_db() as db:
        profile = db.query(PatientProfile).filter_by(user_id=user_id).first()
        if not profile:
            profile = PatientProfile(user_id=user_id)
            db.add(profile)
            db.flush()
        user = db.query(User).filter_by(id=user_id).first()
        result = {
            "patient_profile_id": profile.id,
            "user_id": user_id,
            "name": user.name if user else "Unknown",
            "email": user.email if user else "",
            "phone": profile.phone,
            "date_of_birth": profile.date_of_birth,
            "preferred_language": profile.preferred_language or "English",
            "emergency_contact": profile.emergency_contact,
        }
    log_event("PATIENT_FETCHED", actor_id=actor_id, entity_type="PatientProfile",
              entity_id=result["patient_profile_id"])
    return result


def get_all_patients(actor_role, actor_id):
    if actor_role != "staff":
        raise PermissionError("Only staff can list all patients.")
    with get_db() as db:
        results = (
            db.query(PatientProfile, User)
            .join(User, User.id == PatientProfile.user_id)
            .all()
        )
        return [
            {
                "patient_profile_id": p.id,
                "user_id": p.user_id,
                "name": u.name,
                "email": u.email,
                "phone": p.phone,
                "date_of_birth": p.date_of_birth,
                "created_at": p.created_at.strftime("%Y-%m-%d"),
            }
            for p, u in results
        ]
'''

# ── appointment_service.py ────────────────────────────────────────
appointment = '''import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.database.session import get_db
from app.database.models import Appointment, AppointmentSlot, Doctor, Department, PatientProfile
from app.services.audit_service import log_event

logger = logging.getLogger("agentcare.appointment")

VALID_TRANSITIONS = {
    "pending":     {"confirmed", "cancelled"},
    "confirmed":   {"completed", "cancelled", "rescheduled"},
    "rescheduled": {"confirmed", "cancelled"},
    "completed":   set(),
    "cancelled":   set(),
}


def get_available_slots(department_id, days_ahead=14):
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)
    with get_db() as db:
        results = (
            db.query(AppointmentSlot, Doctor)
            .join(Doctor, Doctor.id == AppointmentSlot.doctor_id)
            .filter(
                Doctor.department_id == department_id,
                Doctor.active == True,
                AppointmentSlot.status == "available",
                AppointmentSlot.start_time >= now,
                AppointmentSlot.start_time <= cutoff,
            )
            .order_by(AppointmentSlot.start_time)
            .all()
        )
        return [
            {
                "slot_id": s.id,
                "doctor_id": d.id,
                "doctor_name": d.name,
                "start_time": s.start_time.strftime("%Y-%m-%d %H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
                "status": s.status,
            }
            for s, d in results
        ]


def check_conflicts(patient_profile_id, slot_id):
    with get_db() as db:
        slot = db.query(AppointmentSlot).filter_by(id=slot_id).first()
        if not slot:
            return {"has_conflict": False, "error": "Slot not found"}
        if slot.status != "available":
            return {"has_conflict": True, "reason": "Slot is already " + slot.status}
        existing = (
            db.query(Appointment)
            .join(AppointmentSlot, AppointmentSlot.id == Appointment.slot_id)
            .filter(
                Appointment.patient_id == patient_profile_id,
                Appointment.status.in_(["pending", "confirmed"]),
                AppointmentSlot.start_time < slot.end_time,
                AppointmentSlot.end_time > slot.start_time,
            )
            .first()
        )
        if existing:
            return {"has_conflict": True, "reason": "Time conflict with existing appointment",
                    "conflicting_appointment_id": existing.id}
        return {"has_conflict": False}


def book_appointment(patient_profile_id, slot_id, reason, actor_role, actor_id):
    if actor_role == "patient" and actor_id != patient_profile_id:
        pass
    conflict = check_conflicts(patient_profile_id, slot_id)
    if conflict.get("has_conflict"):
        return {"success": False, "reason": conflict.get("reason", "Slot unavailable")}
    with get_db() as db:
        slot = db.query(AppointmentSlot).filter_by(id=slot_id).first()
        if not slot or slot.status != "available":
            return {"success": False, "reason": "Slot no longer available."}
        appt = Appointment(
            patient_id=patient_profile_id,
            doctor_id=slot.doctor_id,
            slot_id=slot_id,
            status="confirmed",
            reason=reason,
        )
        db.add(appt)
        slot.status = "booked"
        db.flush()
        result = {
            "success": True,
            "appointment_id": appt.id,
            "slot_id": slot_id,
            "doctor_id": slot.doctor_id,
            "start_time": slot.start_time.strftime("%Y-%m-%d %H:%M"),
            "status": "confirmed",
        }
        logger.info("Appointment booked: id=" + str(appt.id))
    log_event("APPOINTMENT_BOOKED", actor_id=actor_id,
              entity_type="Appointment", entity_id=result["appointment_id"],
              metadata={"slot_id": slot_id, "reason": reason})
    return result


def cancel_appointment(appointment_id, actor_role, actor_id):
    with get_db() as db:
        appt = db.query(Appointment).filter_by(id=appointment_id).first()
        if not appt:
            return {"success": False, "reason": "Appointment not found."}
        if "cancelled" not in VALID_TRANSITIONS.get(appt.status, set()):
            return {"success": False, "reason": "Cannot cancel from status " + appt.status}
        appt.status = "cancelled"
        slot = db.query(AppointmentSlot).filter_by(id=appt.slot_id).first()
        if slot:
            slot.status = "available"
        logger.info("Appointment cancelled: id=" + str(appointment_id))
    log_event("APPOINTMENT_CANCELLED", actor_id=actor_id,
              entity_type="Appointment", entity_id=appointment_id)
    return {"success": True, "appointment_id": appointment_id, "status": "cancelled"}


def get_patient_appointments(patient_profile_id, actor_role, actor_id):
    with get_db() as db:
        results = (
            db.query(Appointment, AppointmentSlot, Doctor, Department)
            .join(AppointmentSlot, AppointmentSlot.id == Appointment.slot_id)
            .join(Doctor, Doctor.id == Appointment.doctor_id)
            .join(Department, Department.id == Doctor.department_id)
            .filter(Appointment.patient_id == patient_profile_id)
            .order_by(AppointmentSlot.start_time.desc())
            .all()
        )
        return [
            {
                "appointment_id": a.id,
                "status": a.status,
                "reason": a.reason,
                "doctor_name": d.name,
                "department": dept.name,
                "start_time": s.start_time.strftime("%Y-%m-%d %H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
                "created_at": a.created_at.strftime("%Y-%m-%d"),
            }
            for a, s, d, dept in results
        ]
'''

# ── document_service.py ───────────────────────────────────────────
document = '''import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.database.session import get_db
from app.database.models import PatientDocument
from app.services.audit_service import log_event
from app.config import UPLOAD_DIR

logger = logging.getLogger("agentcare.document")

REQUIRED_DOCS_BY_DEPARTMENT = {
    "Cardiology":  ["ECG", "BloodReport"],
    "Neurology":   ["ImagingReport"],
    "Orthopedics": ["ImagingReport"],
}

VALID_DOC_TYPES = {
    "ECG", "BloodReport", "ImagingReport",
    "Prescription", "DischargeSummary", "Other"
}


def _compute_checksum(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


def _patient_upload_dir(patient_profile_id):
    patient_dir = UPLOAD_DIR / str(patient_profile_id)
    patient_dir.mkdir(parents=True, exist_ok=True)
    return patient_dir


def check_duplicate(patient_profile_id, checksum):
    with get_db() as db:
        existing = db.query(PatientDocument).filter_by(
            patient_id=patient_profile_id,
            checksum=checksum,
        ).first()
        if existing:
            return {
                "is_duplicate": True,
                "existing_doc_id": existing.id,
                "document_type": existing.document_type,
                "original_filename": existing.original_filename,
                "uploaded_at": existing.created_at.strftime("%Y-%m-%d %H:%M"),
            }
    return None


def store_document(patient_profile_id, file_bytes, original_filename,
                   document_type, document_date, actor_role, actor_id):
    if document_type not in VALID_DOC_TYPES:
        document_type = "Other"
    checksum = _compute_checksum(file_bytes)
    duplicate = check_duplicate(patient_profile_id, checksum)
    if duplicate:
        return {"success": False, "reason": "Duplicate document.", "duplicate": duplicate,
                "document_id": duplicate["existing_doc_id"]}
    safe_name = re.sub(r"[^\\w\\-.]", "_", Path(original_filename).name)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    stored_filename = timestamp + "_" + safe_name
    upload_dir = _patient_upload_dir(patient_profile_id)
    file_path = upload_dir / stored_filename
    file_path.write_bytes(file_bytes)
    relative_path = str(file_path.relative_to(UPLOAD_DIR))
    with get_db() as db:
        doc = PatientDocument(
            patient_id=patient_profile_id,
            document_type=document_type,
            file_path=relative_path,
            original_filename=original_filename,
            document_date=document_date,
            checksum=checksum,
        )
        db.add(doc)
        db.flush()
        doc_id = doc.id
        logger.info("Document stored: id=" + str(doc_id) + " type=" + document_type)
    log_event("DOCUMENT_UPLOADED", actor_id=actor_id,
              entity_type="PatientDocument", entity_id=doc_id,
              metadata={"document_type": document_type, "filename": original_filename})
    return {"success": True, "document_id": doc_id,
            "document_type": document_type, "file_path": relative_path}


def check_missing_documents(patient_profile_id, department_name):
    required = REQUIRED_DOCS_BY_DEPARTMENT.get(department_name, [])
    if not required:
        return {"missing": [], "required": [], "all_present": True}
    with get_db() as db:
        existing_types = {
            row.document_type
            for row in db.query(PatientDocument)
            .filter_by(patient_id=patient_profile_id).all()
        }
    missing = [t for t in required if t not in existing_types]
    return {
        "missing": missing,
        "required": required,
        "present": [t for t in required if t in existing_types],
        "all_present": len(missing) == 0,
    }


def get_patient_documents(patient_profile_id, actor_role, actor_id):
    with get_db() as db:
        docs = (
            db.query(PatientDocument)
            .filter_by(patient_id=patient_profile_id)
            .order_by(PatientDocument.created_at.desc())
            .all()
        )
        return [
            {
                "document_id": d.id,
                "document_type": d.document_type,
                "original_filename": d.original_filename,
                "document_date": d.document_date,
                "uploaded_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for d in docs
        ]
'''

# ── escalation_service.py ─────────────────────────────────────────
escalation = '''import logging
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
'''

# ── reminder_service.py ───────────────────────────────────────────
reminder = '''import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.database.session import get_db
from app.database.models import Reminder, Appointment, AppointmentSlot
from app.services.audit_service import log_event

logger = logging.getLogger("agentcare.reminder")


def create_appointment_reminder(patient_profile_id, appointment_id, actor_id=None):
    with get_db() as db:
        appt = db.query(Appointment).filter_by(id=appointment_id).first()
        if not appt:
            return {"success": False, "reason": "Appointment not found."}
        slot = db.query(AppointmentSlot).filter_by(id=appt.slot_id).first()
        if not slot:
            return {"success": False, "reason": "Slot not found."}
        remind_at = slot.start_time - timedelta(hours=24)
        reminder = Reminder(
            patient_id=patient_profile_id,
            appointment_id=appointment_id,
            reminder_type="appointment",
            message="Reminder: You have an appointment tomorrow at " +
                    slot.start_time.strftime("%H:%M") + ". Please arrive 10 minutes early.",
            scheduled_at=remind_at,
            status="pending",
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id
        remind_str = remind_at.strftime("%Y-%m-%d %H:%M")
        logger.info("Reminder created: id=" + str(reminder_id))
    log_event("REMINDER_CREATED", actor_id=actor_id,
              entity_type="Reminder", entity_id=reminder_id,
              metadata={"appointment_id": appointment_id, "scheduled_at": remind_str})
    return {"success": True, "reminder_id": reminder_id, "scheduled_at": remind_str}


def create_followup_task(patient_profile_id, appointment_id, days_after=7, actor_id=None):
    with get_db() as db:
        appt = db.query(Appointment).filter_by(id=appointment_id).first()
        if not appt:
            return {"success": False, "reason": "Appointment not found."}
        slot = db.query(AppointmentSlot).filter_by(id=appt.slot_id).first()
        base = slot.start_time if slot else datetime.utcnow()
        followup_at = base + timedelta(days=days_after)
        reminder = Reminder(
            patient_id=patient_profile_id,
            appointment_id=appointment_id,
            reminder_type="followup",
            message="Follow-up: It has been " + str(days_after) +
                    " days since your appointment. Please contact your care team if needed.",
            scheduled_at=followup_at,
            status="pending",
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id
        followup_str = followup_at.strftime("%Y-%m-%d")
        logger.info("Followup created: id=" + str(reminder_id))
    log_event("FOLLOWUP_SCHEDULED", actor_id=actor_id,
              entity_type="Reminder", entity_id=reminder_id,
              metadata={"appointment_id": appointment_id, "followup_at": followup_str})
    return {"success": True, "reminder_id": reminder_id, "scheduled_at": followup_str}


def create_missing_docs_reminder(patient_profile_id, missing_doc_types, actor_id=None):
    if not missing_doc_types:
        return {"success": False, "reason": "No missing documents."}
    with get_db() as db:
        doc_list = ", ".join(missing_doc_types)
        reminder = Reminder(
            patient_id=patient_profile_id,
            appointment_id=None,
            reminder_type="document_missing",
            message="Action required: Please upload: " + doc_list,
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            status="pending",
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id
    log_event("MISSING_DOCS_REMINDER", actor_id=actor_id,
              entity_type="Reminder", entity_id=reminder_id,
              metadata={"missing_docs": missing_doc_types})
    return {"success": True, "reminder_id": reminder_id, "missing_docs": missing_doc_types}


def get_patient_reminders(patient_profile_id, actor_role, actor_id):
    with get_db() as db:
        reminders = (
            db.query(Reminder)
            .filter_by(patient_id=patient_profile_id)
            .order_by(Reminder.scheduled_at)
            .all()
        )
        return [
            {
                "reminder_id": r.id,
                "type": r.reminder_type,
                "message": r.message,
                "scheduled_at": r.scheduled_at.strftime("%Y-%m-%d %H:%M"),
                "status": r.status,
                "appointment_id": r.appointment_id,
            }
            for r in reminders
        ]
'''

# ── workflow_service.py ───────────────────────────────────────────
workflow = '''import json
import logging
from datetime import datetime
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
        run.updated_at = datetime.utcnow()
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
'''

# ── Write all files ───────────────────────────────────────────────
files = {
    "app/services/patient_service.py":     patient,
    "app/services/appointment_service.py": appointment,
    "app/services/document_service.py":    document,
    "app/services/escalation_service.py":  escalation,
    "app/services/reminder_service.py":    reminder,
    "app/services/workflow_service.py":    workflow,
}

for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)
    print("Created: " + path)

print("")
print("All service files created.")