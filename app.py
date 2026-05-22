import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from jira_client import fetch_jira_issues
from utils.ui import inject_css, header, footer
from utils.filters import apply_filters
from utils.export import dataframe_to_excel_bytes
# from utils.cache import save_cached_data, load_cached_data, clear_cached_data
# from utils.database import (
#     save_current_snapshot,
#     save_historical_snapshot,
#     load_current_snapshot,
#     clear_current_snapshot
# )
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
    logout_button,
    get_user_role,
    can_refresh_data,
    can_clear_cache,
    can_export_data,
    can_view_raw_data,
    can_view_assignee_workload
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


st.set_page_config(
    page_title="JSM Analyzer",
    page_icon="📊",
    layout="wide"
)

if not login():
    st.stop()

if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = True


def toggle_sidebar():
    st.session_state.sidebar_open = not st.session_state.sidebar_open

col1, col2 = st.columns([0.08, 0.92])
with col1:
    st.button("☰", key="sidebar_open_btn", on_click=toggle_sidebar)


def map_status_category(status):
    status = str(status).strip()

    if status in ["Resolved", "Completed", "Closed", "Canceled", "Cancelled", "Done"]:
        return "Resolved"
    elif status in ["Waiting for customer", "Pending"]:
        return "Pending"
    else:
        return "In Progress"


def prepare_data(df):
    df = df.copy()

    df["Status Category"] = df["Status"].apply(map_status_category)
    df = df[df["Status Category"].isin(["In Progress", "Pending", "Resolved"])]

    df["Created"] = pd.to_datetime(df["Created"], errors="coerce", utc=True)
    df["Updated"] = pd.to_datetime(df["Updated"], errors="coerce", utc=True)

    if "Resolved Date" in df.columns:
        df["Resolved Date"] = pd.to_datetime(df["Resolved Date"], errors="coerce", utc=True)

        df["Resolution Time Days"] = (
            df["Resolved Date"] - df["Created"]
        ).dt.total_seconds() / 86400

        df["Resolution Time Days"] = df["Resolution Time Days"].round(2)
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
    if cached_df is not None:
        st.session_state.jira_df = cached_df
        st.session_state.last_jql = "Loaded from local cache"

# sidebar open/closed state
# if "sidebar_open" not in st.session_state:
#     st.session_state.sidebar_open = True

inject_css(st.session_state.sidebar_open)
header()



with st.sidebar:
    # Navigation header + sidebar toggle (placed near Navigation)
    st.header("📌 Navigation")

    

    role = get_user_role()
    st.caption(f"Role: **{role}**")

    menu_items = [
        "Executive Overview",
        "Executive Intelligence",
        "Historical Intelligence",
        "Status & Queue Health",
        "Aging Analysis",
        "Organization Analysis",
        "Priority Analysis",
        "Issue Type Analysis",
        "Resolution Time Analysis",
        "Trend Analysis",
    ]

    if can_view_assignee_workload():
        menu_items.insert(3, "Assignee Workload")

    # if st.button("Collapse sidebar", key="sidebar_collapse_btn", use_container_width=True):
    #     st.session_state.sidebar_open = False

    # role = get_user_role()
    # st.caption(f"Role: **{role}**")

    menu_items = [
        "Executive Overview",
        "Executive Intelligence",
        "Historical Intelligence",
        "Status & Queue Health",
        "Aging Analysis",
        "Organization Analysis",
        "Priority Analysis",
        "Issue Type Analysis",
        "Resolution Time Analysis",
        "Trend Analysis",
    ]

    if can_view_assignee_workload():
        menu_items.insert(3, "Assignee Workload")

    if can_view_raw_data():
        menu_items.append("Raw Data")

    analysis_view = st.radio(
        "Select analysis view",
        menu_items,
        key="analysis_view"
    )

    # Default values for all roles
    max_results = 2000
    auto_refresh = False
    refresh_minutes = 30

    if can_refresh_data():

        st.divider()
        st.header("🔄 Data Settings")

        max_results = st.number_input(
            "Maximum tickets to fetch",
            min_value=10,
            max_value=5000,
            value=1000,
            step=100,
            key="max_results"
        )

        auto_refresh = st.checkbox(
            "Auto-refresh Jira data",
            value=False,
            key="auto_refresh"
        )

        refresh_minutes = st.number_input(
            "Refresh interval (minutes)",
            min_value=5,
            max_value=120,
            value=30,
            step=5,
            key="refresh_minutes"
        )

        st.divider()
        st.header("🔄 Data Settings")

        max_results = st.number_input(
            "Maximum tickets to fetch",
            min_value=10,
            max_value=5000,
            value=1000,
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



if auto_refresh:
    st_autorefresh(
        interval=refresh_minutes * 60 * 1000,
        key="jira_auto_refresh"
    )


DEFAULT_JQL = "project = KSC ORDER BY created DESC"

load_data = False
clear_data = False
if can_refresh_data() and can_clear_cache():

    with st.expander("🔄 Load Jira Data", expanded=False):

        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            
            load_data = st.button(
                "Fetch / Refresh",
                type="primary",
                use_container_width=True
            )
            

        with col2:
            clear_data = st.button(
            "Clear Data",
            use_container_width=True
        )
        
        with col3:
            if st.session_state.jira_df is not None:
                st.success(f"Loaded: {len(st.session_state.jira_df)} tickets")
            else:
                st.info("No data loaded yet")
else:
    if st.session_state.jira_df is not None:
        st.success(f"Loaded: {len(st.session_state.jira_df)} tickets")
    else:
        st.info("No data loaded yet")


if clear_data:
    st.session_state.jira_df = None
    st.session_state.last_jql = ""
    clear_current_snapshot()

    write_audit_log(
        st.session_state.get("username", ""),
        get_user_role(),
        "CACHE_CLEAR"
    )
    st.warning("Loaded data cleared.")


auto_fetch_triggered = auto_refresh and can_refresh_data()

if load_data or auto_fetch_triggered:
    with st.spinner("Fetching live JSM data..."):
        try:
            df = fetch_jira_issues(DEFAULT_JQL, max_results)
            df = prepare_data(df)

            st.session_state.jira_df = df
            st.session_state.last_jql = DEFAULT_JQL
            save_current_snapshot(df)
            save_historical_snapshot(df)

            write_audit_log(
                st.session_state.get("username", ""),
                get_user_role(),
                "JIRA_REFRESH",
                f"tickets={len(df)}"
            )

            st.success(f"Fetched and saved {len(df)} tickets successfully.")

        except Exception as e:
            st.error("Failed to fetch Jira data.")
            st.exception(e)


df = st.session_state.jira_df

if df is None:
    st.info("No data loaded yet. Ask Support Admin to refresh Jira data.")
    st.stop()


df = prepare_data(df)

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
    safe_render("Executive Overview", executive.render, filtered_df)

elif analysis_view == "Executive Intelligence":
    safe_render("Executive Intelligence", executive_intelligence.render, filtered_df)

elif analysis_view == "Historical Intelligence":
    safe_render(
        "Historical Intelligence",
        historical_intelligence.render,
        filtered_df
    )

elif analysis_view == "Status & Queue Health":
    safe_render("Status & Queue Health", status_analysis.render, filtered_df)

elif analysis_view == "Aging Analysis":
    safe_render("Aging Analysis", aging.render, filtered_df)

elif analysis_view == "Assignee Workload":
    if can_view_assignee_workload():
        safe_render("Assignee Workload", assignee.render, filtered_df)
    else:
        st.warning("You do not have permission to view Assignee Workload.")

elif analysis_view == "Organization Analysis":
    safe_render("Organization Analysis", organization.render, filtered_df)

elif analysis_view == "Priority Analysis":
    safe_render("Priority Analysis", priority.render, filtered_df)

elif analysis_view == "Issue Type Analysis":
    safe_render("Issue Type Analysis", issue_type.render, filtered_df)

elif analysis_view == "Resolution Time Analysis":
    safe_render("Resolution Time Analysis", resolution_time.render, filtered_df)

elif analysis_view == "Trend Analysis":
    safe_render("Trend Analysis", trend_analysis.render, filtered_df)

elif analysis_view == "Raw Data":
    if can_view_raw_data():
        safe_render("Raw Data", raw_data.render, filtered_df)
    else:
        st.warning("You do not have permission to view Raw Data.")

footer()