import streamlit as st
import plotly.express as px
import pandas as pd
from utils.ui import kpi_card

# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

AGE_COLORS = PRIMARY

def render(filtered_df):

    st.subheader("📌 Executive Overview")

    active_df = filtered_df[
        filtered_df["Status Category"].isin(["In Progress", "Pending"])
    ]

    total_tickets = len(filtered_df)
    total_in_progress = len(filtered_df[filtered_df["Status Category"] == "In Progress"])
    total_pending = len(filtered_df[filtered_df["Status Category"] == "Pending"])
    total_resolved = len(filtered_df[filtered_df["Status Category"] == "Resolved"])

    overdue_1_month = len(active_df[active_df["Ticket Age"] > 30])
    overdue_2_months = len(active_df[active_df["Ticket Age"] > 60])

    high_priority_open = len(
        active_df[active_df["Priority"].isin(["High", "Highest"])]
    )

    unassigned_open = len(
        active_df[active_df["Assignee"] == "Unassigned"]
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi_card("Total Tickets", total_tickets, "All filtered tickets", "🎫")

    with c2:
        kpi_card("In Progress", total_in_progress, "Currently active work", "🔵")

    with c3:
        kpi_card("Pending", total_pending, "Waiting / blocked tickets", "🟡")

    with c4:
        kpi_card("Resolved", total_resolved, "Completed tickets", "🟢")

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        kpi_card("Overdue > 1 Month", overdue_1_month, "Open tickets older than 30 days", "🔴")

    with c6:
        kpi_card("Overdue > 2 Months", overdue_2_months, "Critical aging backlog", "⏳")

    with c7:
        kpi_card("High Priority Open", high_priority_open, "High/Highest active tickets", "🚨")

    with c8:
        kpi_card("Unassigned Open", unassigned_open, "Needs owner assignment", "👤")

    st.divider()

    left, right = st.columns(2)

    with left:
        status_summary = filtered_df["Status Category"].value_counts().reset_index()
        status_summary.columns = ["Status Category", "Count"]

        fig = px.pie(
            status_summary,
            names="Status Category",
            values="Count",
            hole=0.5,
            title="Ticket Distribution by Status Category",
            color="Status Category",
            color_discrete_map=STATUS_COLORS
        )

        st.plotly_chart(fig, use_container_width=True)

    with right:
        age_order = [
            "0-2 days",
            "3-5 days",
            "6-10 days",
            "11-20 days",
            "21-30 days",
            "1 to 2 months",
            "> 2 months"
        ]

        aging_summary = active_df["Ticket Age Duration"].value_counts().reset_index()
        aging_summary.columns = ["Ticket Age Duration", "Open Tickets"]

        aging_summary["Ticket Age Duration"] = pd.Categorical(
            aging_summary["Ticket Age Duration"],
            categories=age_order,
            ordered=True
        )

        aging_summary = aging_summary.sort_values("Ticket Age Duration")

        fig = px.bar(
            aging_summary,
            x="Ticket Age Duration",
            y="Open Tickets",
            text="Open Tickets",
            title="Open Ticket Aging Distribution",
            color_discrete_sequence=[AGE_COLORS]
        )

        fig.update_traces(textposition="outside")

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("📍 Executive Interpretation")

    st.info(
        f"""
        The dashboard currently shows **{total_in_progress} In Progress**, 
        **{total_pending} Pending**, and **{total_resolved} Resolved** tickets.  
        There are **{overdue_1_month} open tickets older than one month**, 
        including **{overdue_2_months} tickets older than two months**.  
        These aging tickets should be reviewed first because they indicate backlog risk.
        """
    )