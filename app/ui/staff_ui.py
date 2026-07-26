import logging
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
                            escalation_id=esc["escalation_id"], decision="approved",
                            staff_notes=notes, actor_role=role, actor_id=uid,
                        )
                        st.rerun()
                with col2:
                    if st.button("Reject", key=f"rj_{esc['escalation_id']}"):
                        escalation_service.resolve_escalation(
                            escalation_id=esc["escalation_id"], decision="rejected",
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
