import logging
import time

import streamlit as st
from streamlit_cookies_controller import CookieController

from utils.db_client import get_anon_client, get_scoped_client, bind_session, clear_session
from utils.logger import write_audit_log, count_recent_login_failures


logger = logging.getLogger(__name__)


USER_ROLES_TABLE = "user_roles"
COOKIE_ACCESS = "jsm_access_token"
COOKIE_REFRESH = "jsm_refresh_token"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


def get_cookie_controller():
    return CookieController()


def get_role_by_email(email):
    try:
        client = get_scoped_client()
        response = (
            client.table(USER_ROLES_TABLE)
            .select("role")
            .eq("email", email)
            .single()
            .execute()
        )
        if response.data:
            return response.data.get("role", "slt_viewer")
    except Exception as exc:
        logger.warning("Role lookup failed for %s, defaulting to slt_viewer: %s", email, exc)
        write_audit_log(email, "unknown", "ROLE_LOOKUP_FAILED", str(exc))

    return "slt_viewer"


def initialize_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "username" not in st.session_state:
        st.session_state.username = ""

    if "user_email" not in st.session_state:
        st.session_state.user_email = ""

    if "user_role" not in st.session_state:
        st.session_state.user_role = "slt_viewer"


def restore_session_from_cookie():
    controller = get_cookie_controller()

    access_token = controller.get(COOKIE_ACCESS)
    refresh_token = controller.get(COOKIE_REFRESH)

    if not access_token or not refresh_token:
        return False

    try:
        client = get_anon_client()
        session_response = client.auth.set_session(
            access_token,
            refresh_token
        )

        user = session_response.user

        if not user or not user.email:
            return False

        # Cache this now-authenticated client before the role lookup below,
        # so it runs (and everything else for the rest of this session
        # runs) as this user's own JWT - RLS enforces access as
        # `authenticated`, not the old blanket service-role bypass.
        bind_session(client)

        email = user.email
        role = get_role_by_email(email)

        st.session_state.authenticated = True
        st.session_state.user_email = email
        st.session_state.username = email.split("@")[0]
        st.session_state.user_role = role

        return True

    except Exception:
        controller.remove(COOKIE_ACCESS)
        controller.remove(COOKIE_REFRESH)
        return False


def authenticate_user(email, password, keep_signed_in=True):
    client = get_anon_client()

    auth_response = client.auth.sign_in_with_password(
        {
            "email": email,
            "password": password
        }
    )

    if auth_response.user and auth_response.session:
        bind_session(client)

        role = get_role_by_email(email)

        st.session_state.authenticated = True
        st.session_state.username = email.split("@")[0]
        st.session_state.user_email = email
        st.session_state.user_role = role

        if keep_signed_in:
            controller = get_cookie_controller()

            controller.set(
                COOKIE_ACCESS,
                auth_response.session.access_token,
                max_age=60 * 60 * 12,
                secure=True
            )

            controller.set(
                COOKIE_REFRESH,
                auth_response.session.refresh_token,
                max_age=60 * 60 * 12,
                secure=True
            )

        write_audit_log(
            email,
            role,
            "LOGIN_SUCCESS"
        )

        return True

    return False


def login():
    initialize_auth_state()

    if st.session_state.authenticated:
        return True

    if restore_session_from_cookie():
        return True

    return False


@st.dialog("Internal Login")
def login_modal():
    st.markdown(
        """
        <div style="text-align:center;margin-bottom:16px;">
            <h2 style="color:#02404f;margin-bottom:4px;">🔐 JSM Analyzer</h2>
            <p style="color:#64748b;font-size:14px;">
                Secure access to internal Jira analytics
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    email = st.text_input(
        "Email",
        placeholder="Enter email"
    )

    password = st.text_input(
        "Password",
        type="password",
        placeholder="Enter password"
    )

    keep_signed_in = st.checkbox(
        "Keep me signed in",
        value=True
    )

    if st.button(
        "Login",
        type="primary",
        use_container_width=True
    ):
        recent_failures = count_recent_login_failures(email, LOGIN_LOCKOUT_MINUTES)

        if recent_failures >= MAX_LOGIN_ATTEMPTS:
            st.error(
                f"Too many failed login attempts. Try again in {LOGIN_LOCKOUT_MINUTES} minutes."
            )
        else:
            try:
                if authenticate_user(email, password, keep_signed_in):
                    st.rerun()

            except Exception:
                write_audit_log(
                    email,
                    "unknown",
                    "LOGIN_FAILED"
                )
                st.error("Invalid email or password")


def logout():
    controller = get_cookie_controller()

    email = st.session_state.get("user_email", "")
    role = get_user_role()

    write_audit_log(
        email,
        role,
        "LOGOUT"
    )

    try:
        controller.remove(COOKIE_ACCESS)
        controller.remove(COOKIE_REFRESH)
    except Exception:
        # Cookie removal runs through the component's JS round-trip; a
        # hiccup here shouldn't block logout - session_state below is what
        # actually gates access on the next run.
        pass

    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.user_email = ""
    st.session_state.user_role = "slt_viewer"
    clear_session()

    # Give the cookie-removal component's JS round-trip a moment to actually
    # reach the browser before tearing the script down - rerunning
    # immediately races it and surfaces as a component error.
    time.sleep(0.3)
    st.rerun()


def logout_button():
    with st.sidebar:
        st.divider()
        st.caption(
            f"Logged in as: **{st.session_state.get('user_email', '')}**"
        )

        if st.button("Logout"):
            logout()


def get_user_role():
    return st.session_state.get("user_role", "slt_viewer")


def is_support_admin():
    return get_user_role() in ["support_admin", "admin"]


def is_engineer_pm():
    return get_user_role() == "engineer_pm"


def is_slt():
    return get_user_role() == "slt_viewer"


def can_refresh_data():
    return is_support_admin()


def can_clear_cache():
    return is_support_admin()


def can_export_data():
    return get_user_role() in [
        "support_admin",
        "admin",
        "engineer_pm"
    ]


def can_view_raw_data():
    return get_user_role() in [
        "support_admin",
        "admin",
        "engineer_pm"
    ]


def can_view_assignee_workload():
    return get_user_role() in [
        "support_admin",
        "admin",
        "engineer_pm"
    ]


def can_manage_incidents():
    return get_user_role() in [
        "support_admin",
        "admin",
        "engineer_pm"
    ]