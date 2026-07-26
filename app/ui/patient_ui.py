import logging
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
