import streamlit as st
from datetime import datetime
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