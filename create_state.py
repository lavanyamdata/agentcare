import os

content = '''from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # ── Who is this request for ──────────────────────────────
    user_id: int                    # logged-in user (User table)
    patient_profile_id: int         # their patient profile (PatientProfile table)
    actor_role: str                 # "patient" or "staff"
    user_message: str               # what the patient typed

    # ── Workflow tracking ────────────────────────────────────
    workflow_run_id: int            # which WorkflowRun row in DB tracks this run

    # ── Safety Agent writes these ────────────────────────────
    is_safe: bool                   # True = safe to proceed, False = escalate
    escalation_reason: str          # why it was escalated (empty if safe)

    # ── Routing Agent writes these ───────────────────────────
    department: str                 # e.g. "Cardiology"
    department_id: int              # FK to Department table

    # ── Appointment Agent writes these ───────────────────────
    slot_id: int                    # chosen appointment slot
    appointment_id: int             # created appointment row

    # ── Coordinator writes this last ─────────────────────────
    final_response: str             # message shown to patient at end

    # ── Any agent can write here ─────────────────────────────
    errors: List[str]               # accumulates errors across all agents
'''

os.makedirs("app/orchestrator", exist_ok=True)

with open("app/orchestrator/__init__.py", "w", encoding="utf-8") as f:
    f.write("")

with open("app/orchestrator/state.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Created: app/orchestrator/__init__.py")
print("Created: app/orchestrator/state.py")
print("Done.")