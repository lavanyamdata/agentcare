import logging
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
