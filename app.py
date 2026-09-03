import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from jira_client import fetch_jira_issues
from utils.ui import inject_css, header, footer
from utils.filters import apply_filters
from utils.export import dataframe_to_excel_bytes
from utils.supabase_db import (
    save_current_snapshot,
    save_historical_snapshot,
    load_current_snapshot,
    clear_current_snapshot
)
from utils.logger import write_audit_log
from utils.safe_render import safe_render

from utils.auth import (
    login,
    login_modal,
    logout_button,
    get_user_role,
    can_refresh_data,
    can_clear_cache,
    can_export_data,
    can_view_raw_data,
    can_view_assignee_workload,
    is_support_admin
)

from pages_view import executive
from pages_view import status_analysis
from pages_view import aging
from pages_view import assignee
from pages_view import organization
from pages_view import priority
from pages_view import trend_analysis
from pages_view import raw_data
from pages_view import issue_type
from pages_view import resolution_time
from pages_view import executive_intelligence
from pages_view import historical_intelligence
from pages_view import public_dashboard
from pages_view import label_analysis
from pages_view import incident_impact
from pages_view import ga4_activity
from pages_view import support_triage

from PIL import Image

favicon = Image.open("assets/favicon.ico")

st.set_page_config(
    page_title="JSM Analyzer",
    page_icon=favicon,
    layout="wide"
)

inject_css()

authenticated = login()

if not authenticated:
    col1, col2 = st.columns([6, 1])

    with col2:
        if st.button("🔐 Internal Login", width="stretch"):
            login_modal()

    public_dashboard.render()
    st.stop()


def map_status_category(status):
    status = str(status).strip()

    if status in [
        "Resolved",
        "Completed",
        "Closed",
        "Canceled",
        "Cancelled",
        "Done"
    ]:
        return "Resolved"

    elif status in [
        "Waiting for customer",
        "Pending"
    ]:
        return "Pending"

    else:
        return "In Progress"


def prepare_data(df):
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    if df.empty:
        return pd.DataFrame()

    df.columns = [str(col).strip() for col in df.columns]

    required_defaults = {
        "Issue Type": "Unknown",
        "Key": "",
        "Summary": "",
        "Assignee": "Unassigned",
        "Reporter": "",
        "Priority": "Unknown",
        "Status": "Unknown",
        "Labels": "Unlabeled",
        "Resolution": "",
        "Created": pd.NaT,
        "Updated": pd.NaT,
        "Due date": pd.NaT,
        "Organizations": "Unknown",
        "Ticket Age": 0,
        "Ticket Age Duration": "Unknown",
        "Overdue": "Unknown"
    }

    for col, default_value in required_defaults.items():
        if col not in df.columns:
            df[col] = default_value

    if "status" in df.columns and df["Status"].eq("Unknown").all():
        df["Status"] = df["status"]

    df["Ticket Age"] = pd.to_numeric(
        df["Ticket Age"],
        errors="coerce"
    ).fillna(0)

    df["Status Category"] = df["Status"].apply(map_status_category)

    df = df[
        df["Status Category"].isin(
            ["In Progress", "Pending", "Resolved"]
        )
    ]

    df["Created"] = pd.to_datetime(
        df["Created"],
        errors="coerce",
        utc=True
    )

    df["Updated"] = pd.to_datetime(
        df["Updated"],
        errors="coerce",
        utc=True
    )

    if "Resolved Date" in df.columns:
        df["Resolved Date"] = pd.to_datetime(
            df["Resolved Date"],
            errors="coerce",
            utc=True
        )

        df["Resolution Time Days"] = (
            df["Resolved Date"] - df["Created"]
        ).dt.total_seconds() / 86400

        df["Resolution Time Days"] = (
            df["Resolution Time Days"]
            .round(2)
        )

    else:
        df["Resolution Time Days"] = None

    df["Year"] = df["Created"].dt.year
    df["Month"] = df["Created"].dt.strftime("%B")
    df["Year-Month"] = df["Created"].dt.to_period("M").astype(str)

    return df


if "jira_df" not in st.session_state:
    st.session_state.jira_df = None

if "last_jql" not in st.session_state:
    st.session_state.last_jql = ""


if st.session_state.jira_df is None:
    cached_df = load_current_snapshot()

    if cached_df is not None and not cached_df.empty:
        st.session_state.jira_df = cached_df
        st.session_state.last_jql = "Loaded from Supabase"


header()


with st.sidebar:
    st.header("Navigation")

    role = get_user_role()
    st.caption(f"Role: **{role}**")
    st.caption(
        f"User: **{st.session_state.get('user_email', '')}**"
    )

    menu_items = [
        "Executive Overview",
        "Executive Intelligence",
        "Historical Intelligence",
        "Status & Queue Health",
        "Aging Analysis",
        "Organization Analysis",
        "Priority Analysis",
        "Label / Category Analysis",
        "Issue Type Analysis",
        "Resolution Time Analysis",
        "Incident Impact Assessment",
        "GA4 Activity Baseline",
        "Trend Analysis",
    ]

    if can_view_assignee_workload():
        menu_items.insert(3, "Assignee Workload")

    if is_support_admin():
        menu_items.append("Support Triage")

    if can_view_raw_data():
        menu_items.append("Raw Data")

    analysis_view = st.radio(
        "Select analysis view",
        menu_items
    )

    max_results = 2000
    auto_refresh = False
    refresh_minutes = 30

    if can_refresh_data():
        st.divider()
        st.header("Data Settings")

        max_results = st.number_input(
            "Maximum tickets to fetch",
            min_value=100,
            max_value=5000,
            value=2000,
            step=100
        )

        auto_refresh = st.checkbox(
            "Auto-refresh Jira data",
            value=False
        )

        refresh_minutes = st.number_input(
            "Refresh interval (minutes)",
            min_value=5,
            max_value=120,
            value=30,
            step=5
        )

logout_button()


if auto_refresh and can_refresh_data():
    st_autorefresh(
        interval=refresh_minutes * 60 * 1000,
        key="jira_auto_refresh"
    )


DEFAULT_JQL = "project = KSC ORDER BY created DESC"
# DEFAULT_JQL = "project = KSC AND created >= -30d ORDER BY created DESC"
# DEFAULT_JQL = "project = KSC AND created >= -365d ORDER BY created DESC"

load_data = False
clear_data = False


if can_refresh_data() and can_clear_cache():

    with st.expander("🔄 Load Jira Data", expanded=False):

        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            load_data = st.button(
                "Fetch / Refresh",
                type="primary",
                width="stretch"
            )

        with col2:
            clear_data = st.button(
                "Clear Data",
                width="stretch"
            )

        with col3:
            if st.session_state.jira_df is not None:
                st.success(
                    f"Loaded: {len(st.session_state.jira_df)} tickets"
                )
            else:
                st.info("No data loaded yet")

else:
    if st.session_state.jira_df is not None:
        st.success(
            f"Loaded: {len(st.session_state.jira_df)} tickets"
        )
    else:
        st.info("No data loaded yet")


if clear_data:
    st.session_state.jira_df = None
    st.session_state.last_jql = ""

    clear_current_snapshot()

    write_audit_log(
        st.session_state.get("user_email", ""),
        get_user_role(),
        "CACHE_CLEAR"
    )

    st.warning("Loaded data cleared.")


auto_fetch_triggered = (
    auto_refresh
    and can_refresh_data()
)

if load_data or auto_fetch_triggered:

    with st.spinner("Fetching live JSM data..."):

        try:
            df = fetch_jira_issues(
                DEFAULT_JQL,
                max_results
            )
            

            df = prepare_data(df)

            if df.empty:
                st.warning("Jira data was fetched, but no valid ticket records were found.")
            else:
                st.session_state.jira_df = df
                st.session_state.last_jql = DEFAULT_JQL

                save_current_snapshot(df)
                save_historical_snapshot(df)

                write_audit_log(
                    st.session_state.get("user_email", ""),
                    get_user_role(),
                    "JIRA_REFRESH",
                    f"tickets={len(df)}"
                )

                st.success(
                    f"Fetched and saved {len(df)} tickets successfully."
                )

        except Exception as e:
            st.error("Failed to fetch Jira data.")
            st.exception(e)


df = st.session_state.jira_df

if df is None:
    st.info(
        "No data loaded yet. Ask Support Admin to refresh Jira data."
    )
    st.stop()


df = prepare_data(df)

if df.empty:
    st.warning(
        "Loaded data is empty or missing required Jira fields. Please ask Support Admin to refresh Jira data."
    )
    st.stop()


st.caption(
    f"✅ Loaded dataset: **{len(df)} tickets** | Source: KSC Jira Service Management"
)


filtered_df = apply_filters(df)


excel_data = dataframe_to_excel_bytes(filtered_df)

if can_export_data():
    st.download_button(
        label="⬇️ Download Filtered Data as Excel",
        data=excel_data,
        file_name="jsm_filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.caption("Export disabled for this role.")


if analysis_view == "Executive Overview":
    safe_render(
        "Executive Overview",
        executive.render,
        filtered_df
    )

elif analysis_view == "Executive Intelligence":
    safe_render(
        "Executive Intelligence",
        executive_intelligence.render,
        filtered_df
    )

elif analysis_view == "Historical Intelligence":
    safe_render(
        "Historical Intelligence",
        historical_intelligence.render,
        filtered_df
    )

elif analysis_view == "Status & Queue Health":
    safe_render(
        "Status & Queue Health",
        status_analysis.render,
        filtered_df
    )

elif analysis_view == "Aging Analysis":
    safe_render(
        "Aging Analysis",
        aging.render,
        filtered_df
    )

elif analysis_view == "Assignee Workload":
    if can_view_assignee_workload():
        safe_render(
            "Assignee Workload",
            assignee.render,
            filtered_df
        )
    else:
        st.warning(
            "You do not have permission to view Assignee Workload."
        )

elif analysis_view == "Organization Analysis":
    safe_render(
        "Organization Analysis",
        organization.render,
        filtered_df
    )

elif analysis_view == "Priority Analysis":
    safe_render(
        "Priority Analysis",
        priority.render,
        filtered_df
    )
elif analysis_view == "Label / Category Analysis":
    safe_render(
        "Label / Category Analysis",
        label_analysis.render,
        filtered_df
    )

elif analysis_view == "Issue Type Analysis":
    safe_render(
        "Issue Type Analysis",
        issue_type.render,
        filtered_df
    )

elif analysis_view == "Resolution Time Analysis":
    safe_render(
        "Resolution Time Analysis",
        resolution_time.render,
        filtered_df
    )

elif analysis_view == "Incident Impact Assessment":
    safe_render(
        "Incident Impact Assessment",
        incident_impact.render,
        filtered_df
    )

elif analysis_view == "GA4 Activity Baseline":
    safe_render(
        "GA4 Activity Baseline",
        ga4_activity.render,
        filtered_df
    )

elif analysis_view == "Trend Analysis":
    safe_render(
        "Trend Analysis",
        trend_analysis.render,
        filtered_df
    )

elif analysis_view == "Support Triage":
    if is_support_admin():
        safe_render(
            "Support Triage",
            support_triage.render,
            filtered_df
        )
    else:
        st.warning(
            "You do not have permission to view Support Triage."
        )

elif analysis_view == "Raw Data":
    if can_view_raw_data():
        safe_render(
            "Raw Data",
            raw_data.render,
            filtered_df
        )
    else:
        st.warning(
            "You do not have permission to view Raw Data."
        )

footer()
