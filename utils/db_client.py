import streamlit as st
from supabase import create_client


def get_anon_client():
    """A fresh, unauthenticated Supabase client (RLS sees this as `anon`).

    Safe for the public dashboard and for pre-login calls (e.g. the login
    rate-limit counter, or logging a failed login attempt before any
    session exists).
    """
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def get_scoped_client():
    """The current Streamlit session's authenticated Supabase client if one
    has been bound (RLS sees `authenticated` + this user's own JWT, so the
    database enforces access itself instead of trusting the app not to have
    a bug), otherwise a bare anon client.

    Deliberately keyed on `_db_client` alone, not `st.session_state.authenticated`
    - that flag is set by the caller only after the role lookup that itself
    depends on this function, so gating on it here would make this client
    unauthenticated for that very first lookup.
    """
    bound = st.session_state.get("_db_client")
    if bound is not None:
        return bound

    return get_anon_client()


def bind_session(client):
    """Cache an already-authenticated client (post sign-in / cookie
    restore) so get_scoped_client() can reuse it for the rest of this
    Streamlit session, instead of re-authenticating on every query.
    """
    st.session_state["_db_client"] = client


def clear_session():
    st.session_state.pop("_db_client", None)
