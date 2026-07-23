import logging
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
