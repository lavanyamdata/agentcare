import streamlit as st
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
                    profile.id if profile else None
                )
            st.rerun()

    with st.expander("Demo accounts"):
        st.code("Patient: ravi@example.com / Patient@123\nStaff:   admin@agentcare.dev / Staff@123")


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
