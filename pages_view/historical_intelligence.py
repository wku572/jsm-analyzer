import streamlit as st
import pandas as pd
import plotly.express as px

from utils.supabase_db import load_historical_snapshots
from utils.ui import kpi_card

# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = {
    "Open": ACCENT,
    "Resolved": SUCCESS
}

ACTIVE_BACKLOG_COLOR = ACCENT
AGING_COLORS = {
    "Overdue > 1 Month": "#EAB308",  # amber
    "Overdue > 2 Months": "#DC2626"  # red
}
RISK_COLORS = {
    "High Priority Open": "#F59E0B",  # orange-500
    "Unassigned Open": "#EF4444"      # red-500
}


# Jira's status rename split the old "pending" bucket into In Progress plus
# three waiting_for_* buckets, and froze several old snapshot columns at 0
# from that point forward while the matching new columns were 0 by column
# default before it (they didn't exist yet). Summing an old+new pair like
# this is seamless across the cutover without needing to know its date:
# whichever side of the cutover a row is on, exactly one half is real and
# the other is 0.
def _combined(row, *columns):
    return sum(int(row.get(col, 0) or 0) for col in columns)

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

    # Build continuity columns that read correctly whether a given snapshot
    # was taken before or after the Jira status-rename cutover.
    hist_df["Open"] = hist_df.apply(
        lambda r: _combined(
            r, "in_progress", "pending",
            "waiting_for_customer", "waiting_for_support", "waiting_for_approval"
        ),
        axis=1
    )
    hist_df["Open Backlog"] = hist_df.apply(
        lambda r: _combined(r, "active_backlog", "open_total"), axis=1
    )
    hist_df["Overdue > 1 Month"] = hist_df.apply(
        lambda r: _combined(r, "overdue_1_month", "open_overdue_1_month"), axis=1
    )
    hist_df["Overdue > 2 Months"] = hist_df.apply(
        lambda r: _combined(r, "overdue_2_months", "open_overdue_2_months"), axis=1
    )
    hist_df["High Priority Open"] = hist_df.apply(
        lambda r: _combined(r, "high_priority_open", "open_high_priority"), axis=1
    )
    hist_df["Unassigned Open"] = hist_df.apply(
        lambda r: _combined(r, "unassigned_open", "open_unassigned"), axis=1
    )

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
            "Latest Open",
            int(latest["Open"]),
            "In Progress + Waiting for customer/support/approval",
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

    trend_df = hist_df.rename(columns={"resolved": "Resolved"}).melt(
        id_vars=["snapshot_timestamp"],
        value_vars=["Open", "Resolved"],
        var_name="Status Category",
        value_name="Tickets"
    )

    fig = px.line(
        trend_df,
        x="snapshot_timestamp",
        y="Tickets",
        color="Status Category",
        markers=True,
        title="Operational Queue Trend",
        color_discrete_map=STATUS_COLORS
    )

    fig.update_layout(height=430)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("## 📌 Active Backlog Growth")

    fig2 = px.area(
        hist_df,
        x="snapshot_timestamp",
        y="Open Backlog",
        title="Active Backlog Trend",
        color_discrete_sequence=[ACTIVE_BACKLOG_COLOR]
    )

    fig2.update_layout(height=380)
    st.plotly_chart(fig2, use_container_width=True)

    left, right = st.columns(2)

    with left:
        st.markdown("## 🚨 Aging Risk Trend")

        aging_df = hist_df.melt(
            id_vars=["snapshot_timestamp"],
            value_vars=["Overdue > 1 Month", "Overdue > 2 Months"],
            var_name="Aging Category",
            value_name="Tickets"
        )

        fig3 = px.line(
            aging_df,
            x="snapshot_timestamp",
            y="Tickets",
            color="Aging Category",
            markers=True,
            title="Overdue Ticket Trend",
            color_discrete_map=AGING_COLORS
        )

        fig3.update_layout(height=380)
        st.plotly_chart(fig3, use_container_width=True)

    with right:
        st.markdown("## ⚠️ Risk Indicators")

        risk_df = hist_df.melt(
            id_vars=["snapshot_timestamp"],
            value_vars=["High Priority Open", "Unassigned Open"],
            var_name="Risk Type",
            value_name="Tickets"
        )

        fig4 = px.line(
            risk_df,
            x="snapshot_timestamp",
            y="Tickets",
            color="Risk Type",
            markers=True,
            title="Operational Risk Trend",
            color_discrete_map=RISK_COLORS
        )

        fig4.update_layout(height=380)
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    st.markdown("## 🧾 Historical Snapshot Table")

    display_cols = [
        "snapshot_timestamp",
        "total_tickets",
        "in_progress",
        "Open",
        "resolved",
        "Open Backlog",
        "Overdue > 1 Month",
        "Overdue > 2 Months",
        "High Priority Open",
        "Unassigned Open"
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
            last["Open Backlog"] - first["Open Backlog"]
        )

        resolved_change = int(
            last.get("resolved", 0)
            - first.get("resolved", 0)
        )

        overdue_change = int(
            last["Overdue > 1 Month"] - first["Overdue > 1 Month"]
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