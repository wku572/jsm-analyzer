import streamlit as st
import bcrypt

from utils.logger import write_audit_log


SESSION_TOKEN = "jsm_logged_in"


def check_password(password, hashed_password):
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def is_logged_in_from_url():
    return st.query_params.get("auth") == SESSION_TOKEN


def login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "username" not in st.session_state:
        st.session_state.username = ""

    if is_logged_in_from_url():
        st.session_state.authenticated = True
        return True

    if st.session_state.authenticated:
        return True

    left, center, right = st.columns([1.5, 2, 1.5])

    with center:
        st.markdown("<br><br>", unsafe_allow_html=True)

        st.markdown(
            """
            <h1 style="
                text-align:center;
                font-size:48px;
                font-weight:800;
                margin-bottom:10px;
                color:#02404f;
                font-family:Montserrat,sans-serif;
            ">
                🔐 JSM Analyzer
            </h1>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <p style="
                text-align:center;
                color:#64748b;
                margin-bottom:28px;
                font-size:15px;
            ">
                Secure access to Kifiya Jira Service Management Analytics
            </p>
            """,
            unsafe_allow_html=True
        )

        with st.container(border=True):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")

            login_btn = st.button(
                "Login",
                type="primary",
                use_container_width=True
            )

        if login_btn:
            users = st.secrets["auth"]["users"]

            if username in users:
                stored_hash = users[username]["password_hash"]

                if check_password(password, stored_hash):
                    st.session_state.authenticated = True
                    st.session_state.username = username

                    st.query_params["auth"] = SESSION_TOKEN
                  
                    role = users[username].get("role", "slt_viewer")
                    write_audit_log(username, role, "LOGIN_SUCCESS")
                    st.rerun()
            write_audit_log(username, "unknown", "LOGIN_FAILED")
            st.error("Invalid username or password")

    return False


def logout_button():
    with st.sidebar:
        st.divider()
        st.caption(f"Logged in as: **{st.session_state.get('username', '')}**")

        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = ""

            if "auth" in st.query_params:
                del st.query_params["auth"]
            
            write_audit_log(
                st.session_state.get("username", ""),
                get_user_role(),
                "LOGOUT"
            )
            st.rerun()


def get_user_role():
    username = st.session_state.get("username", "")

    if not username:
        return "slt_viewer"

    users = st.secrets["auth"]["users"]

    if username in users:
        return users[username].get("role", "slt_viewer")

    return "slt_viewer"


def is_support_admin():
    return get_user_role() == "support_admin"


def is_engineer_pm():
    return get_user_role() == "engineer_pm"


def is_slt():
    return get_user_role() == "slt_viewer"


def can_refresh_data():
    return is_support_admin()


def can_clear_cache():
    return is_support_admin()


def can_export_data():
    return get_user_role() in ["support_admin", "engineer_pm"]


def can_view_raw_data():
    return get_user_role() in ["support_admin", "engineer_pm"]


def can_view_assignee_workload():
    return get_user_role() in ["support_admin", "engineer_pm"]