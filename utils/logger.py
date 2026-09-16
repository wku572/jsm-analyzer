import streamlit as st
from datetime import datetime, timedelta
import pytz
from supabase import create_client


LOCAL_TZ = "Africa/Addis_Ababa"
AUDIT_TABLE = "audit_logs"


def get_client():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_role_key"]
    return create_client(url, key)


def write_audit_log(username, role, action, details=""):
    try:
        client = get_client()

        tz = pytz.timezone(LOCAL_TZ)
        timestamp = datetime.now(tz).isoformat()

        payload = {
            "created_at": timestamp,
            "username": username or "",
            "role": role or "",
            "action": action or "",
            "details": details or ""
        }

        client.table(AUDIT_TABLE).insert(payload).execute()

    except Exception:
        # Never crash the app because logging failed
        pass


def count_recent_login_failures(username, minutes=15):
    try:
        client = get_client()

        tz = pytz.timezone(LOCAL_TZ)
        cutoff = (datetime.now(tz) - timedelta(minutes=minutes)).isoformat()

        response = (
            client.table(AUDIT_TABLE)
            .select("id", count="exact")
            .eq("username", username or "")
            .eq("action", "LOGIN_FAILED")
            .gte("created_at", cutoff)
            .execute()
        )

        return response.count or 0

    except Exception:
        # Fail open on the counter itself - a broken count check should
        # never be the reason a legitimate user can't log in.
        return 0