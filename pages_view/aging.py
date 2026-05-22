import streamlit as st
import plotly.express as px
import pandas as pd


def render(filtered_df):

    st.subheader("⏳ Aging Analysis")

    active_df = filtered_df[
        filtered_df["Status Category"].isin(["In Progress", "Pending"])
    ]

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
        title="Open Tickets by Aging Bucket"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    old_tickets = active_df.sort_values("Ticket Age", ascending=False)

    st.subheader("🧓 Oldest Open Tickets")

    st.dataframe(
        old_tickets[
            [
                "Key", "Summary", "Assignee", "Priority",
                "Status", "Status Category", "Ticket Age",
                "Ticket Age Duration", "Organizations"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    overdue_30 = len(active_df[active_df["Ticket Age"] > 30])
    overdue_60 = len(active_df[active_df["Ticket Age"] > 60])

    st.subheader("📍 Aging Interpretation")

    st.warning(
        f"""
        There are **{overdue_30} open tickets older than one month** and 
        **{overdue_60} open tickets older than two months**.  
        These tickets should be reviewed with assignees because long aging usually indicates 
        blocked work, missing follow-up, unclear ownership, or unresolved dependency.
        """
    )