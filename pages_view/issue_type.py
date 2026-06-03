import streamlit as st
import plotly.express as px

# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

def render(filtered_df):

    st.subheader("🧩 Issue Type Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    issue_summary = filtered_df.pivot_table(
        index="Issue Type",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    for col in ["In Progress", "Pending", "Resolved"]:
        if col not in issue_summary.columns:
            issue_summary[col] = 0

    issue_summary["Open Tickets"] = (
        issue_summary["In Progress"] + issue_summary["Pending"]
    )

    issue_summary["Total"] = (
        issue_summary["In Progress"] +
        issue_summary["Pending"] +
        issue_summary["Resolved"]
    )

    issue_summary = issue_summary.sort_values("Total", ascending=False)

    fig = px.bar(
        issue_summary,
        x="Issue Type",
        y=["In Progress", "Pending", "Resolved"],
        title="Tickets by Issue Type and Status Category",
        barmode="group",
        color_discrete_map=STATUS_COLORS
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(issue_summary, use_container_width=True, hide_index=True)

    top_issue = issue_summary.iloc[0]["Issue Type"]
    top_total = issue_summary.iloc[0]["Total"]
    top_open = issue_summary.iloc[0]["Open Tickets"]

    st.subheader("📍 Issue Type Interpretation")

    st.info(
        f"""
        **{top_issue}** is the most frequent issue type with **{top_total} total tickets**, 
        including **{top_open} currently open tickets**.  
        If this issue type repeatedly dominates the queue, it may indicate either a product instability area, 
        unclear user guidance, weak intake classification, or a recurring operational dependency.  
        The support team should review whether these tickets are isolated cases or symptoms of a repeated root cause.
        """
    )