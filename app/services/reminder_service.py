import logging
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
