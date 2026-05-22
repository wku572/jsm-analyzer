import streamlit as st
import pandas as pd
import plotly.express as px

# from utils.database import load_historical_snapshots
from utils.supabase_db import load_historical_snapshots


PRIMARY = "#02404f"
ACCENT = "#eb7d23"


def card(title, value, note="", color=PRIMARY):
    st.markdown(
        f"""
        <div style="
            background:white;
            padding:18px;
            border-radius:18px;
            border-left:6px solid {color};
            box-shadow:0 8px 24px rgba(15,23,42,0.06);
            min-height:120px;
        ">
            <div style="
                color:#64748b;
                font-size:12px;
                font-weight:800;
                text-transform:uppercase;
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
                color:#94a3b8;
                font-size:12px;
                margin-top:8px;
            ">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render(_filtered_df=None):

    st.markdown("## 📈 Historical Intelligence")

    hist_df = load_historical_snapshots()

    if hist_df is None or hist_df.empty:
        st.info("No historical snapshot data available.")
        return

    hist_df["snapshot_timestamp"] = pd.to_datetime(
        hist_df["snapshot_timestamp"],
        errors="coerce"
    )

    hist_df = hist_df.dropna(subset=["snapshot_timestamp"])

    hist_df["snapshot_period"] = (
        hist_df["snapshot_timestamp"].dt.strftime("%Y-%m-%d %H:%M")
    )

    snapshot_summary = (
        hist_df.groupby(["snapshot_period", "Status Category"])
        .size()
        .reset_index(name="count")
    )

    grouped = (
        snapshot_summary.pivot_table(
            index="snapshot_period",
            columns="Status Category",
            values="count",
            fill_value=0
        )
        .reset_index()
    )

    grouped.columns.name = None

    for col in ["In Progress", "Pending", "Resolved"]:
        if col not in grouped.columns:
            grouped[col] = 0

    grouped["total_tickets"] = (
        grouped["In Progress"] +
        grouped["Pending"] +
        grouped["Resolved"]
    )

    grouped["active_backlog"] = grouped["In Progress"] + grouped["Pending"]
    grouped = grouped.sort_values("snapshot_period")

    latest = grouped.iloc[-1]
    snapshot_count = grouped["snapshot_period"].nunique()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card("Latest Total Tickets", int(latest["total_tickets"]), "Latest stored snapshot", PRIMARY)

    with c2:
        card("Latest In Progress", int(latest["In Progress"]), "Active execution queue", "#2563eb")

    with c3:
        card("Latest Pending", int(latest["Pending"]), "Waiting / dependency queue", "#f59e0b")

    with c4:
        card("Latest Resolved", int(latest["Resolved"]), "Completed ticket volume", "#16a34a")

    st.markdown(
        f"""
        <div style="
            margin-top:18px;
            margin-bottom:22px;
            padding:16px 18px;
            border-radius:14px;
            background:#f8fafc;
            border:1px solid #e2e8f0;
            color:#475569;
            font-size:13px;
            line-height:1.5;
        ">
            Historical Intelligence is based on stored Jira snapshots. Current available snapshot periods:
            <b>{snapshot_count}</b>. Trend charts become more meaningful after multiple refreshes across time.
        </div>
        """,
        unsafe_allow_html=True
    )

    if snapshot_count < 2:
        st.warning(
            "Only one snapshot period is available. Trend lines will appear as points until more snapshots are collected."
        )

    st.divider()

    st.markdown("### 📊 Queue Evolution Over Time")

    melted = grouped.melt(
        id_vars="snapshot_period",
        value_vars=["In Progress", "Pending", "Resolved"],
        var_name="Status Category",
        value_name="Ticket Count"
    )

    fig = px.line(
        melted,
        x="snapshot_period",
        y="Ticket Count",
        color="Status Category",
        markers=True,
        title="Operational Queue Trend"
    )

    fig.update_traces(line=dict(width=3), marker=dict(size=9))
    fig.update_layout(
        height=430,
        xaxis_title="Snapshot Time",
        yaxis_title="Tickets",
        legend_title="Status Category",
        xaxis_tickangle=-35,
        margin=dict(l=20, r=20, t=55, b=90)
    )

    st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)

    with left:
        st.markdown("### 📌 Active Backlog Growth")

        fig2 = px.area(
            grouped,
            x="snapshot_period",
            y="active_backlog",
            title="Active Backlog Trend"
        )

        fig2.update_layout(
            height=390,
            xaxis_title="Snapshot Time",
            yaxis_title="Active Backlog",
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=55, b=90)
        )

        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.markdown("### 🏦 Top Organization Trend")

        org_trend = (
            hist_df.groupby(["snapshot_period", "Organizations"])
            .size()
            .reset_index(name="Tickets")
        )

        top_orgs = (
            org_trend.groupby("Organizations")["Tickets"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
            .index
        )

        org_trend = org_trend[org_trend["Organizations"].isin(top_orgs)]

        fig3 = px.line(
            org_trend,
            x="snapshot_period",
            y="Tickets",
            color="Organizations",
            markers=True,
            title="Top Organizations Trend"
        )

        fig3.update_traces(line=dict(width=3), marker=dict(size=8))
        fig3.update_layout(
            height=390,
            xaxis_title="Snapshot Time",
            yaxis_title="Tickets",
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=55, b=90)
        )

        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    st.markdown("### 📋 Historical Snapshot Table")

    st.dataframe(
        grouped,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### 💡 Historical Insights")

    first = grouped.iloc[0]

    backlog_change = int(latest["active_backlog"] - first["active_backlog"])
    resolved_change = int(latest["Resolved"] - first["Resolved"])

    if backlog_change > 0:
        backlog_direction = "increased"
    elif backlog_change < 0:
        backlog_direction = "decreased"
    else:
        backlog_direction = "remained stable"

    st.info(
        f"""
        Historical snapshots show that the active backlog has **{backlog_direction}**
        by **{abs(backlog_change)} tickets** over the observed period.

        Resolved ticket volume changed by **{resolved_change} tickets**.

        Since only stored snapshots are analyzed here, this page becomes more valuable as snapshots accumulate over hours, days, and weeks.
        """
    )