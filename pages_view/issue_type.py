import streamlit as st
import plotly.express as px

# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Waiting for customer": ACCENT,
    "Waiting for support": "#2563eb",
    "Waiting for approval": "#7c3aed",
    "Resolved": SUCCESS
}

OPEN_SUB_STATUSES = [
    "In Progress",
    "Waiting for customer",
    "Waiting for support",
    "Waiting for approval"
]


def render(filtered_df):

    st.subheader("🧩 Issue Type Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    open_df = filtered_df[filtered_df["Status Category"] == "Open"]

    issue_summary = open_df.pivot_table(
        index="Issue Type",
        columns="Status",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    for col in OPEN_SUB_STATUSES:
        if col not in issue_summary.columns:
            issue_summary[col] = 0

    resolved_counts = (
        filtered_df[filtered_df["Status Category"] == "Resolved"]
        .groupby("Issue Type")["Key"]
        .count()
    )
    issue_summary["Resolved"] = issue_summary["Issue Type"].map(resolved_counts).fillna(0).astype(int)

    issue_summary["Open Tickets"] = issue_summary[OPEN_SUB_STATUSES].sum(axis=1)

    issue_summary["Total"] = issue_summary["Open Tickets"] + issue_summary["Resolved"]

    issue_summary = issue_summary.sort_values("Total", ascending=False)

    fig = px.bar(
        issue_summary,
        x="Issue Type",
        y=OPEN_SUB_STATUSES + ["Resolved"],
        title="Tickets by Issue Type and Status",
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