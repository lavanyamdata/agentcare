main_py = '''import streamlit as st
from app.auth.rbac import authenticate_user, get_patient_profile_for_user

st.set_page_config(page_title="AgentCare", page_icon="🏥", layout="wide")


def login_page():
    st.title("🏥 AgentCare")
    st.caption("Agentic AI for Patient Administration - no medical advice, admin only")

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        user = authenticate_user(email, password)
        if user is None:
            st.error("Invalid email or password")
        else:
            st.session_state["user_id"] = user.id
            st.session_state["name"] = user.name
            st.session_state["role"] = user.role
            if user.role == "patient":
                profile = get_patient_profile_for_user(user.id)
                st.session_state["patient_profile_id"] = (
                    profile["patient_profile_id"] if profile else None
                )
            st.rerun()

    with st.expander("Demo accounts"):
        st.code("Patient: ravi@example.com / Patient@123\\nStaff:   admin@agentcare.dev / Staff@123")


def main():
    if "user_id" not in st.session_state:
        login_page()
        return

    st.sidebar.write(f"**{st.session_state['name']}** ({st.session_state['role']})")
    if st.sidebar.button("Log out"):
        st.session_state.clear()
        st.rerun()

    if st.session_state["role"] == "staff":
        from app.ui.staff_ui import render_staff_ui
        render_staff_ui()
    else:
        from app.ui.patient_ui import render_patient_ui
        render_patient_ui()


main()
'''

patient_py = '''import logging
from datetime import date
import streamlit as st
from app.orchestrator.graph import run_agentcare_workflow
from app.services import appointment_service, document_service, reminder_service

logger = logging.getLogger("agentcare.ui.patient")


def render_patient_ui():
    st.title("Patient Portal")
    uid = st.session_state["user_id"]
    role = st.session_state["role"]
    ppid = st.session_state.get("patient_profile_id")

    tab_request, tab_appts, tab_docs, tab_reminders = st.tabs(
        ["New Request", "My Appointments", "My Documents", "My Reminders"]
    )

    with tab_request:
        st.subheader("Submit an administrative request")
        st.caption("Example: I need a cardiology appointment next week")
        msg = st.text_area("What do you need?", height=100)
        if st.button("Submit request", type="primary"):
            if not msg.strip():
                st.warning("Please enter a request first.")
            else:
                with st.spinner("Agents processing your request..."):
                    try:
                        result = run_agentcare_workflow(
                            user_id=uid, actor_role=role, user_message=msg.strip()
                        )
                        st.success(result["final_response"])
                        if result["appointment_id"]:
                            st.info(f"Appointment ID: {result['appointment_id']} | Department: {result['department']}")
                        if result["errors"]:
                            st.warning("Some steps had issues: " + "; ".join(result["errors"]))
                    except Exception as e:
                        logger.error(f"Workflow failed: {e}")
                        st.error("Something went wrong processing your request. Staff have been notified.")

    with tab_appts:
        st.subheader("My appointments")
        try:
            appts = appointment_service.get_patient_appointments(
                patient_profile_id=ppid, actor_role=role, actor_id=uid
            )
            if appts:
                st.dataframe(appts, use_container_width=True)
            else:
                st.info("No appointments yet.")
        except Exception as e:
            st.error(f"Could not load appointments: {e}")

    with tab_docs:
        st.subheader("Upload a document")
        up = st.file_uploader("Choose file", type=["pdf", "png", "jpg", "jpeg", "txt"])
        doc_type = st.selectbox("Document type", ["ECG", "Blood Report", "Prescription", "Referral", "Other"])
        doc_date = st.date_input("Document date", value=date.today())
        if st.button("Upload") and up is not None:
            try:
                result = document_service.store_document(
                    patient_profile_id=ppid,
                    file_bytes=up.getvalue(),
                    original_filename=up.name,
                    document_type=doc_type,
                    document_date=str(doc_date),
                    actor_role=role,
                    actor_id=uid,
                )
                if result.get("duplicate"):
                    st.warning("This document was already uploaded (duplicate detected).")
                else:
                    st.success(f"Stored: {up.name} as {doc_type}")
            except Exception as e:
                st.error(f"Upload failed: {e}")

        st.divider()
        st.subheader("My documents")
        try:
            docs = document_service.get_patient_documents(
                patient_profile_id=ppid, actor_role=role, actor_id=uid
            )
            if docs:
                st.dataframe(docs, use_container_width=True)
            else:
                st.info("No documents uploaded yet.")
        except Exception as e:
            st.error(f"Could not load documents: {e}")

    with tab_reminders:
        st.subheader("My reminders and follow-ups")
        try:
            reminders = reminder_service.get_patient_reminders(
                patient_profile_id=ppid, actor_role=role, actor_id=uid
            )
            if reminders:
                st.dataframe(reminders, use_container_width=True)
            else:
                st.info("No reminders yet.")
        except Exception as e:
            st.error(f"Could not load reminders: {e}")
'''

staff_py = '''import logging
import streamlit as st
from app.services import escalation_service, workflow_service, audit_service

logger = logging.getLogger("agentcare.ui.staff")


def render_staff_ui():
    st.title("Staff Dashboard")
    uid = st.session_state["user_id"]
    role = st.session_state["role"]

    tab_esc, tab_runs, tab_audit = st.tabs(
        ["Escalations", "Workflow Runs", "Audit Log"]
    )

    with tab_esc:
        st.subheader("Pending escalations")
        try:
            pending = escalation_service.get_pending_escalations(actor_role=role, actor_id=uid)
        except Exception as e:
            st.error(f"Could not load escalations: {e}")
            pending = []

        if not pending:
            st.success("No pending escalations.")
        for esc in pending:
            with st.container(border=True):
                st.write(f"**Escalation #{esc['escalation_id']}** — workflow run {esc['workflow_run_id']}")
                st.write(f"Reason: {esc['reason']}")
                notes = st.text_input("Staff notes", key=f"notes_{esc['escalation_id']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Approve", key=f"ap_{esc['escalation_id']}"):
                        escalation_service.resolve_escalation(
                            escalation_id=esc["escalation_id"], decision="approve",
                            staff_notes=notes, actor_role=role, actor_id=uid,
                        )
                        st.rerun()
                with col2:
                    if st.button("Reject", key=f"rj_{esc['escalation_id']}"):
                        escalation_service.resolve_escalation(
                            escalation_id=esc["escalation_id"], decision="reject",
                            staff_notes=notes, actor_role=role, actor_id=uid,
                        )
                        st.rerun()

        st.divider()
        st.subheader("All escalations")
        try:
            all_esc = escalation_service.get_all_escalations(actor_role=role, actor_id=uid)
            if all_esc:
                st.dataframe(all_esc, use_container_width=True)
        except Exception as e:
            st.error(f"Could not load escalation history: {e}")

    with tab_runs:
        st.subheader("All workflow runs")
        try:
            runs = workflow_service.get_all_workflow_runs(actor_role=role)
            if runs:
                st.dataframe(runs, use_container_width=True)
            else:
                st.info("No workflow runs yet.")
        except Exception as e:
            st.error(f"Could not load workflow runs: {e}")

    with tab_audit:
        st.subheader("Audit log (latest 100)")
        try:
            events = audit_service.get_audit_log(limit=100)
            if events:
                st.dataframe(events, use_container_width=True)
            else:
                st.info("No audit events yet.")
        except Exception as e:
            st.error(f"Could not load audit log: {e}")
'''

import os
os.makedirs("app/ui", exist_ok=True)
with open("app/ui/__init__.py", "w", encoding="utf-8") as f:
    f.write("")
with open("app/ui/patient_ui.py", "w", encoding="utf-8") as f:
    f.write(patient_py)
with open("app/ui/staff_ui.py", "w", encoding="utf-8") as f:
    f.write(staff_py)
with open("main.py", "w", encoding="utf-8") as f:
    f.write(main_py)
print("Created: app/ui/patient_ui.py")
print("Created: app/ui/staff_ui.py")
print("Created: main.py  (project root)")