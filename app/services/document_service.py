import hashlib
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
    safe_name = re.sub(r"[^\w\-.]", "_", Path(original_filename).name)
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
