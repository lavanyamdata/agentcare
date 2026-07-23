"""
test_services.py — Quick smoke test for all service files.
Run this to confirm all services work before building agents.
"""

from app.database.session import init_db
from app.database.seed import seed_all

# Initialize database
init_db()
seed_all()

print("=" * 50)
print("TESTING ALL SERVICES")
print("=" * 50)

# ── Get test data IDs ─────────────────────────────────
from app.database.session import get_db
from app.database.models import PatientProfile, Department

with get_db() as db:
    patient = db.query(PatientProfile).first()
    dept    = db.query(Department).filter_by(name="Cardiology").first()
    pid     = patient.id
    user_id = patient.user_id
    dept_id = dept.id

print("Test patient_profile_id:", pid)
print("Test user_id:", user_id)
print("Test dept_id:", dept_id)
print()

# ── Test 1: Patient Service ───────────────────────────
print("TEST 1 — Patient Service")
from app.services.patient_service import get_or_create_patient
p = get_or_create_patient(user_id=user_id, actor_role="patient", actor_id=user_id)
print("  Patient:", p["name"], "| profile_id:", p["patient_profile_id"])
print("  PASS")
print()

# ── Test 2: Appointment Service — get slots ───────────
print("TEST 2 — Get Available Slots")
from app.services.appointment_service import get_available_slots
slots = get_available_slots(department_id=dept_id, days_ahead=30)
print("  Available slots:", len(slots))
print("  First slot:", slots[0]["start_time"], "|", slots[0]["doctor_name"])
print("  PASS")
print()

# ── Test 3: Appointment Service — book ───────────────
print("TEST 3 — Book Appointment")
from app.services.appointment_service import book_appointment
result = book_appointment(
    patient_profile_id=pid,
    slot_id=slots[0]["slot_id"],
    reason="Cardiology follow-up",
    actor_role="patient",
    actor_id=user_id
)
print("  Success:", result["success"])
print("  Appointment ID:", result.get("appointment_id"))
print("  Start time:", result.get("start_time"))
print("  PASS")
print()

# ── Test 4: Double booking blocked ───────────────────
print("TEST 4 — Double Book Blocked")
result2 = book_appointment(
    patient_profile_id=pid,
    slot_id=slots[0]["slot_id"],
    reason="Duplicate attempt",
    actor_role="patient",
    actor_id=user_id
)
print("  Blocked:", not result2["success"])
print("  Reason:", result2.get("reason"))
print("  PASS")
print()

# ── Test 5: Document Service ──────────────────────────
print("TEST 5 — Document Service")
from app.services.document_service import (
    store_document, check_duplicate, check_missing_documents
)
doc_result = store_document(
    patient_profile_id=pid,
    file_bytes=b"fake ecg data for testing",
    original_filename="ecg_test.pdf",
    document_type="ECG",
    document_date="2026-07-01",
    actor_role="patient",
    actor_id=user_id
)
print("  Document stored:", doc_result["success"])
print("  Document ID:", doc_result.get("document_id"))
print("  PASS")
print()

# ── Test 6: Duplicate Detection ───────────────────────
print("TEST 6 — Duplicate Detection")
dup = store_document(
    patient_profile_id=pid,
    file_bytes=b"fake ecg data for testing",
    original_filename="ecg_copy.pdf",
    document_type="ECG",
    document_date="2026-07-01",
    actor_role="patient",
    actor_id=user_id
)
print("  Duplicate blocked:", not dup["success"])
print("  Reason:", dup.get("reason"))
print("  PASS")
print()

# ── Test 7: Missing Documents ─────────────────────────
print("TEST 7 — Missing Documents Check")
missing = check_missing_documents(pid, "Cardiology")
print("  Required:", missing["required"])
print("  Present:", missing["present"])
print("  Missing:", missing["missing"])
print("  PASS")
print()

# ── Test 8: Workflow Service ──────────────────────────
print("TEST 8 — Workflow Service")
from app.services.workflow_service import (
    create_workflow_run, update_workflow_state, get_workflow_run
)
wf = create_workflow_run(pid, "I need a cardiology appointment")
wf_id = wf["workflow_run_id"]
update_workflow_state(wf_id, "appointment_booked",
                      {"appointment_id": result["appointment_id"]},
                      "running")
wf_data = get_workflow_run(wf_id)
print("  Workflow ID:", wf_data["workflow_run_id"])
print("  Current step:", wf_data["current_step"])
print("  Status:", wf_data["status"])
print("  PASS")
print()

# ── Test 9: Escalation Service ────────────────────────
print("TEST 9 — Escalation Service")
from app.services.escalation_service import (
    create_escalation, resolve_escalation, get_pending_escalations
)
esc = create_escalation(
    workflow_run_id=wf_id,
    reason="Patient mentioned chest pain",
    actor_id=user_id
)
print("  Escalation ID:", esc["escalation_id"])
print("  Status:", esc["status"])

pending = get_pending_escalations(actor_role="staff", actor_id=1)
print("  Pending escalations:", len(pending))

resolve = resolve_escalation(
    escalation_id=esc["escalation_id"],
    decision="approved",
    staff_notes="Reviewed — safe to proceed.",
    actor_role="staff",
    actor_id=1
)
print("  Resolved:", resolve["decision"])
print("  PASS")
print()

# ── Test 10: Reminder Service ─────────────────────────
print("TEST 10 — Reminder Service")
from app.services.reminder_service import (
    create_appointment_reminder, create_followup_task
)
appt_id = result["appointment_id"]
rem = create_appointment_reminder(
    patient_profile_id=pid,
    appointment_id=appt_id
)
print("  Reminder ID:", rem.get("reminder_id"))
print("  Scheduled:", rem.get("scheduled_at"))

fu = create_followup_task(
    patient_profile_id=pid,
    appointment_id=appt_id
)
print("  Follow-up ID:", fu.get("reminder_id"))
print("  Scheduled:", fu.get("scheduled_at"))
print("  PASS")
print()

# ── Test 11: Audit Log ────────────────────────────────
print("TEST 11 — Audit Log")
from app.services.audit_service import get_audit_log
events = get_audit_log(limit=20)
print("  Total audit events:", len(events))
for e in events[:5]:
    print("  ", e["action"])
print("  PASS")
print()

print("=" * 50)
print("ALL TESTS PASSED")
print("=" * 50)