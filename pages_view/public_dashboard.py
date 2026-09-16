import base64
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz

from utils.supabase_db import load_current_snapshot
from utils.ui import PRIMARY, ACCENT, LOGO_PATH


# Brand colors - shared with the rest of the app (utils/ui.py) so the public
# page and the authenticated app read as one product, not two.
SUCCESS = "#22C55E"
DANGER = "#dc2626"
INFO_BLUE = "#2563eb"
WARN_AMBER = "#f59e0b"

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

SUMMARY_COLORS = PRIMARY

LOCAL_TZ = "Africa/Addis_Ababa"

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Raleway, sans-serif", color="#334155", size=13),
    title_font=dict(family="Montserrat, sans-serif", color=PRIMARY, size=15),
)


def public_kpi_card(title, value, note, color, icon="📌"):
    st.markdown(
        f"""
        <div style="
            background:white;
            border-radius:18px;
            padding:20px;
            border-top:5px solid {color};
            border-left:1px solid #e2e8f0;
            border-right:1px solid #e2e8f0;
            border-bottom:1px solid #e2e8f0;
            box-shadow:0 8px 24px rgba(15,23,42,0.06);
            min-height:130px;
        ">
            <div style="
                color:#64748b;
                font-size:12px;
                font-weight:800;
                text-transform:uppercase;
                letter-spacing:.5px;
            ">
                {icon} {title}
            </div>
            <div style="
                color:{PRIMARY};
                font-size:34px;
                font-weight:900;
                margin-top:8px;
                font-family:'Montserrat', sans-serif;
            ">
                {value}
            </div>
            <div style="
                color:#94a3b8;
                font-size:11px;
                margin-top:8px;
                line-height:1.4;
            ">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _style_chart(fig, height=420, bottom_margin=60):
    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=50, b=bottom_margin),
        **CHART_LAYOUT
    )
    fig.update_xaxes(gridcolor="#eef2f6")
    fig.update_yaxes(gridcolor="#eef2f6")
    return fig


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


@st.cache_data
def _logo_data_uri():
    path = Path(LOGO_PATH)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def render():

    last_updated = get_last_updated()

    hero_col, updated_col = st.columns([5, 1.25])

    with hero_col:
        logo_uri = _logo_data_uri()
        logo_html = (
            f"""
            <span style="
                background:white;
                border-radius:12px;
                padding:6px 12px;
                display:inline-flex;
                align-items:center;
                margin-right:16px;
            ">
                <img src="{logo_uri}" style="height:32px; display:block;" />
            </span>
            """
            if logo_uri else ""
        )

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
                    display:flex;
                    align-items:center;
                    font-size:34px;
                    font-weight:900;
                    margin-bottom:6px;
                    font-family:'Montserrat', sans-serif;
                ">
                    {logo_html}JSM Public Operations Dashboard
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
                    ⏱️ Last Updated
                </div>
                <div style="
                    margin-top:10px;
                    color:{PRIMARY};
                    font-size:18px;
                    font-weight:800;
                    line-height:1.35;
                    font-family:'Montserrat', sans-serif;
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

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        public_kpi_card(
            "Total Tickets",
            total_tickets,
            "All tracked Jira tickets",
            PRIMARY,
            "🗂️"
        )

    with c2:
        public_kpi_card(
            "In Progress",
            in_progress,
            "Currently active work",
            INFO_BLUE,
            "🔵"
        )

    with c3:
        public_kpi_card(
            "Pending",
            pending,
            "Waiting or dependency queue",
            WARN_AMBER,
            "🟡"
        )

    with c4:
        public_kpi_card(
            "Resolved",
            resolved,
            "Completed ticket volume",
            SUCCESS,
            "🟢"
        )

    with c5:
        public_kpi_card(
            "Overdue > 1 Month",
            overdue_1m,
            "Open tickets older than 30 days",
            DANGER,
            "🔴"
        )

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    resolved_rate = round((resolved / total_tickets) * 100, 1) if total_tickets else 0
    pending_rate = round((pending / total_tickets) * 100, 1) if total_tickets else 0
    active_rate = round(((in_progress + pending) / total_tickets) * 100, 1) if total_tickets else 0

    st.markdown(
        f"""
        <div style="
            background:#eef6fb;
            border:1px solid #d3e6f0;
            border-radius:18px;
            padding:20px 24px;
            box-shadow:0 8px 24px rgba(15,23,42,0.04);
        ">
            <div style="
                font-weight:800;
                font-size:14px;
                color:{PRIMARY};
                text-transform:uppercase;
                letter-spacing:.04em;
                margin-bottom:10px;
            ">
                📌 Executive Summary
            </div>
            <div style="color:#1e3a4c; font-size:14.5px; line-height:1.7;">
                The current Jira Service Management queue contains <b>{total_tickets} total tickets</b>.
                Of these, <b>{resolved_rate}% are resolved</b>, while <b>{active_rate}% remain active</b>
                across In Progress and Pending categories.
                <br><br>
                Pending tickets represent <b>{pending_rate}%</b> of the total queue.
                There are <b>{overdue_1m} open tickets older than one month</b>, which should be monitored as an operational backlog risk.
                <br><br>
                <span style="color:#64748b; font-size:13px;">
                    This public view provides high-level visibility only and does not expose ticket details,
                    customer information, or internal Jira records.
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            st.markdown("#### 📊 Status Distribution")

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
                hole=0.55,
                title="Ticket Status Distribution",
                color="Status Category",
                color_discrete_map=STATUS_COLORS
            )
            fig.update_traces(textfont=dict(family="Raleway, sans-serif"))

            st.plotly_chart(_style_chart(fig, bottom_margin=20), use_container_width=True)

    with right:
        with st.container(border=True):
            st.markdown("#### 🏦 Top Organizations")

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

            fig2.update_traces(textposition="outside", marker_line_width=0)
            fig2.update_layout(xaxis_tickangle=-35)

            st.plotly_chart(_style_chart(fig2, bottom_margin=100), use_container_width=True)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### 🧩 Issue Type Summary")

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

        fig4.update_traces(textposition="outside", marker_line_width=0)
        fig4.update_layout(xaxis_tickangle=-35)

        st.plotly_chart(_style_chart(fig4, bottom_margin=100), use_container_width=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div style="
            border-top:1px solid #e2e8f0;
            padding-top:18px;
            text-align:center;
        ">
            <div style="color:#64748b; font-size:12.5px;">
                🔒 Public dashboard: aggregated metrics only. Detailed ticket records are available only to authenticated users.
            </div>
            <div style="color:#94a3b8; font-size:11px; margin-top:6px;">
                © 2026 Kifiya Financial Technology &bull; JSM Analytics Platform
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
