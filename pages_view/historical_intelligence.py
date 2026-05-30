import streamlit as st
import pandas as pd
import plotly.express as px

from utils.supabase_db import load_historical_snapshots
from utils.ui import kpi_card


def render(data=None):
    st.markdown("# 📈 Historical Intelligence")

    hist_df = load_historical_snapshots()

    if hist_df is None or hist_df.empty:
        st.info("No historical snapshot data available.")
        return

    hist_df = hist_df.copy()

    if "snapshot_timestamp" not in hist_df.columns:
        st.warning("Historical snapshot table is missing snapshot_timestamp.")
        return

    hist_df["snapshot_timestamp"] = pd.to_datetime(
        hist_df["snapshot_timestamp"],
        errors="coerce"
    )

    hist_df = hist_df.dropna(subset=["snapshot_timestamp"])
    hist_df = hist_df.sort_values("snapshot_timestamp")

    if hist_df.empty:
        st.info("No valid historical snapshot timestamps found.")
        return

    latest = hist_df.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi_card(
            "Latest Total Tickets",
            int(latest.get("total_tickets", 0)),
            "Latest stored snapshot",
            "📦"
        )

    with c2:
        kpi_card(
            "Latest In Progress",
            int(latest.get("in_progress", 0)),
            "Active execution queue",
            "🔵"
        )

    with c3:
        kpi_card(
            "Latest Pending",
            int(latest.get("pending", 0)),
            "Waiting / dependency queue",
            "🟡"
        )

    with c4:
        kpi_card(
            "Latest Resolved",
            int(latest.get("resolved", 0)),
            "Completed ticket volume",
            "🟢"
        )

    st.info(
        f"Historical Intelligence is based on stored Jira summary snapshots. "
        f"Current available snapshot periods: {len(hist_df)}. "
        f"Trend charts become more meaningful after multiple refreshes across time."
    )

    st.divider()

    st.markdown("## 📊 Queue Evolution Over Time")

    trend_df = hist_df.melt(
        id_vars=["snapshot_timestamp"],
        value_vars=["in_progress", "pending", "resolved"],
        var_name="Status Category",
        value_name="Tickets"
    )

    fig = px.line(
        trend_df,
        x="snapshot_timestamp",
        y="Tickets",
        color="Status Category",
        markers=True,
        title="Operational Queue Trend"
    )

    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("## 📌 Active Backlog Growth")

    fig2 = px.area(
        hist_df,
        x="snapshot_timestamp",
        y="active_backlog",
        title="Active Backlog Trend"
    )

    fig2.update_layout(height=380)
    st.plotly_chart(fig2, use_container_width=True)

    left, right = st.columns(2)

    with left:
        st.markdown("## 🚨 Aging Risk Trend")

        aging_cols = [
            col for col in ["overdue_1_month", "overdue_2_months"]
            if col in hist_df.columns
        ]

        if aging_cols:
            aging_df = hist_df.melt(
                id_vars=["snapshot_timestamp"],
                value_vars=aging_cols,
                var_name="Aging Category",
                value_name="Tickets"
            )

            fig3 = px.line(
                aging_df,
                x="snapshot_timestamp",
                y="Tickets",
                color="Aging Category",
                markers=True,
                title="Overdue Ticket Trend"
            )

            fig3.update_layout(height=380)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No aging trend data available.")

    with right:
        st.markdown("## ⚠️ Risk Indicators")

        risk_cols = [
            col for col in ["high_priority_open", "unassigned_open"]
            if col in hist_df.columns
        ]

        if risk_cols:
            risk_df = hist_df.melt(
                id_vars=["snapshot_timestamp"],
                value_vars=risk_cols,
                var_name="Risk Type",
                value_name="Tickets"
            )

            fig4 = px.line(
                risk_df,
                x="snapshot_timestamp",
                y="Tickets",
                color="Risk Type",
                markers=True,
                title="Operational Risk Trend"
            )

            fig4.update_layout(height=380)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No risk indicator data available.")

    st.divider()

    st.markdown("## 🧾 Historical Snapshot Table")

    display_cols = [
        "snapshot_timestamp",
        "total_tickets",
        "in_progress",
        "pending",
        "resolved",
        "active_backlog",
        "overdue_1_month",
        "overdue_2_months",
        "high_priority_open",
        "unassigned_open"
    ]

    existing_cols = [
        col for col in display_cols
        if col in hist_df.columns
    ]

    st.dataframe(
        hist_df[existing_cols].sort_values(
            "snapshot_timestamp",
            ascending=False
        ),
        use_container_width=True
    )

    st.markdown("## 💡 Historical Insights")

    if len(hist_df) >= 2:
        first = hist_df.iloc[0]
        last = hist_df.iloc[-1]

        backlog_change = int(
            last.get("active_backlog", 0)
            - first.get("active_backlog", 0)
        )

        resolved_change = int(
            last.get("resolved", 0)
            - first.get("resolved", 0)
        )

        overdue_change = int(
            last.get("overdue_1_month", 0)
            - first.get("overdue_1_month", 0)
        )

        st.info(
            f"""
            Historical snapshots show that active backlog changed by **{backlog_change} tickets**
            across the observed period.

            Resolved ticket volume changed by **{resolved_change} tickets**.

            Open tickets older than one month changed by **{overdue_change} tickets**.

            These insights become stronger as more snapshots are collected over time.
            """
        )

    else:
        st.info(
            "Only one historical snapshot is available. More refreshes over time are needed for meaningful trend analysis."
        )