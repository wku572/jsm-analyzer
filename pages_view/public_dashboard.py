import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz

from utils.supabase_db import load_current_snapshot


# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

SUMMARY_COLORS = PRIMARY

LOCAL_TZ = "Africa/Addis_Ababa"


def public_kpi_card(title, value, note, color):
    st.markdown(
        f"""
        <div style="
            background:white;
            border-radius:18px;
            padding:20px;
            border-left:6px solid {color};
            box-shadow:0 8px 24px rgba(15,23,42,0.06);
            min-height:120px;
        ">
            <div style="
                color:#64748b;
                font-size:12px;
                font-weight:800;
                text-transform:uppercase;
                letter-spacing:.5px;
            ">
                {title}
            </div>
            <div style="
                color:{PRIMARY};
                font-size:34px;
                font-weight:900;
                margin-top:8px;
            ">
                {value}
            </div>
            <div style="
                color:#64748b;
                font-size:12px;
                margin-top:8px;
                line-height:1.4;
            ">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def prepare_public_data(df):
    df = df.copy()

    df["Ticket Age"] = pd.to_numeric(
        df.get("Ticket Age", 0),
        errors="coerce"
    ).fillna(0)

    return df


def get_last_updated():
    tz = pytz.timezone(LOCAL_TZ)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")


def render():

    last_updated = get_last_updated()

    hero_col, updated_col = st.columns([5, 1.25])

    with hero_col:
        st.markdown(
            f"""
            <div style="
                background:linear-gradient(135deg, {PRIMARY}, #03596d);
                color:white;
                padding:28px 32px;
                border-radius:24px;
                margin-bottom:24px;
                box-shadow:0 12px 32px rgba(2,64,79,0.25);
            ">
                <div style="
                    font-size:34px;
                    font-weight:900;
                    margin-bottom:6px;
                ">
                    📊 JSM Public Operations Dashboard
                </div>
                <div style="
                    font-size:15px;
                    color:#dbeafe;
                    line-height:1.5;
                ">
                    High-level operational visibility for Jira Service Management performance.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with updated_col:
        st.markdown(
            f"""
            <div style="
                background:white;
                border-radius:20px;
                padding:18px;
                text-align:center;
                box-shadow:0 8px 24px rgba(15,23,42,0.08);
                border:1px solid #e2e8f0;
                margin-top:6px;
                min-height:110px;
            ">
                <div style="
                    font-size:11px;
                    color:#64748b;
                    font-weight:700;
                    text-transform:uppercase;
                    letter-spacing:.8px;
                ">
                    Last Updated
                </div>
                <div style="
                    margin-top:10px;
                    color:{PRIMARY};
                    font-size:18px;
                    font-weight:800;
                    line-height:1.35;
                ">
                    {last_updated}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    df = load_current_snapshot()

    if df is None or df.empty:
        st.info("No public dashboard data is available yet.")
        return

    df = prepare_public_data(df)

    total_tickets = len(df)
    in_progress = len(df[df["Status Category"] == "In Progress"])
    pending = len(df[df["Status Category"] == "Pending"])
    resolved = len(df[df["Status Category"] == "Resolved"])

    active_df = df[df["Status Category"].isin(["In Progress", "Pending"])]
    overdue_1m = len(active_df[active_df["Ticket Age"] > 30])

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        public_kpi_card(
            "Total Tickets",
            total_tickets,
            "All tracked Jira tickets",
            PRIMARY
        )

    with c2:
        public_kpi_card(
            "In Progress",
            in_progress,
            "Currently active work",
            "#2563eb"
        )

    with c3:
        public_kpi_card(
            "Pending",
            pending,
            "Waiting or dependency queue",
            "#f59e0b"
        )

    with c4:
        public_kpi_card(
            "Resolved",
            resolved,
            "Completed ticket volume",
            "#16a34a"
        )

    with c5:
        public_kpi_card(
            "Overdue > 1 Month",
            overdue_1m,
            "Open tickets older than 30 days",
            "#dc2626"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    st.markdown("### 📌 Executive Summary")

    resolved_rate = round((resolved / total_tickets) * 100, 1) if total_tickets else 0
    pending_rate = round((pending / total_tickets) * 100, 1) if total_tickets else 0
    active_rate = round(((in_progress + pending) / total_tickets) * 100, 1) if total_tickets else 0

    st.info(
        f"""
        The current Jira Service Management queue contains **{total_tickets} total tickets**.
        Of these, **{resolved_rate}% are resolved**, while **{active_rate}% remain active**
        across In Progress and Pending categories.

        Pending tickets represent **{pending_rate}%** of the total queue. 
        There are **{overdue_1m} open tickets older than one month**, which should be monitored as an operational backlog risk.

        This public view provides high-level visibility only and does not expose ticket details, customer information, or internal Jira records.
        """
    )

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown("### 📊 Status Distribution")

        status_summary = (
            df["Status Category"]
            .value_counts()
            .reset_index()
        )
        status_summary.columns = ["Status Category", "Tickets"]

        fig = px.pie(
            status_summary,
            names="Status Category",
            values="Tickets",
            hole=0.45,
            title="Ticket Status Distribution",
            color="Status Category",
            color_discrete_map=STATUS_COLORS
        )

        fig.update_layout(
            height=430,
            margin=dict(l=20, r=20, t=60, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### 🏦 Top Organizations")

        org_summary = (
            df.groupby("Organizations")
            .size()
            .reset_index(name="Tickets")
            .sort_values("Tickets", ascending=False)
            .head(10)
        )

        fig2 = px.bar(
            org_summary,
            x="Organizations",
            y="Tickets",
            text="Tickets",
            title="Top Organizations by Ticket Volume",
            color_discrete_sequence=[SUMMARY_COLORS]
        )

        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            height=430,
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=60, b=100)
        )

        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left2, right2 = st.columns(2)

    with left2:
        st.markdown("### 👤 Assignee Workload Summary")

        assignee_summary = (
            active_df.groupby("Assignee")
            .size()
            .reset_index(name="Active Tickets")
            .sort_values("Active Tickets", ascending=False)
            .head(10)
        )

        fig3 = px.bar(
            assignee_summary,
            x="Assignee",
            y="Active Tickets",
            text="Active Tickets",
            title="Top Active Workload by Assignee",
            color_discrete_sequence=[SUMMARY_COLORS]
        )

        fig3.update_traces(textposition="outside")
        fig3.update_layout(
            height=430,
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=60, b=100)
        )

        st.plotly_chart(fig3, use_container_width=True)

    with right2:
        st.markdown("### 🧩 Issue Type Summary")

        issue_summary = (
            df.groupby("Issue Type")
            .size()
            .reset_index(name="Tickets")
            .sort_values("Tickets", ascending=False)
            .head(10)
        )

        fig4 = px.bar(
            issue_summary,
            x="Issue Type",
            y="Tickets",
            text="Tickets",
            title="Top Issue Types",
            color_discrete_sequence=[SUMMARY_COLORS]
        )

        fig4.update_traces(textposition="outside")
        fig4.update_layout(
            height=430,
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=60, b=100)
        )

        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    st.caption(
        "Public dashboard: aggregated metrics only. Detailed ticket records are available only to authenticated users."
    )