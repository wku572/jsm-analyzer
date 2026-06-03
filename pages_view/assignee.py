import streamlit as st
import plotly.express as px

from pages_view.historical_intelligence import STATUS_COLORS

# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange

STATUS_COLORS = {
    "In_Progress": PRIMARY,
    "Pending": ACCENT
}
def render(filtered_df):

    st.subheader("👤 Assignee Workload Analysis")

    active_df = filtered_df[
        filtered_df["Status Category"].isin(["In Progress", "Pending"])
    ]

    if active_df.empty:
        st.info("No active tickets found for the selected filters.")
        return

    assignee_summary = active_df.groupby("Assignee").agg(
        Open_Tickets=("Key", "count"),
        In_Progress=("Status Category", lambda x: (x == "In Progress").sum()),
        Pending=("Status Category", lambda x: (x == "Pending").sum()),
        Overdue_1_Month=("Ticket Age", lambda x: (x > 30).sum()),
        Overdue_2_Months=("Ticket Age", lambda x: (x > 60).sum()),
        Average_Age=("Ticket Age", "mean"),
        Oldest_Ticket=("Ticket Age", "max")
    ).reset_index()

    assignee_summary["Average_Age"] = assignee_summary["Average_Age"].round(1)
    assignee_summary = assignee_summary.sort_values("Open_Tickets", ascending=False)

    fig = px.bar(
        assignee_summary,
        x="Assignee",
        y=["In_Progress", "Pending"],
        title="Open Tickets by Assignee",
        barmode="stack",
        color_discrete_map=STATUS_COLORS
    )

    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Assignee Workload Table")

    st.dataframe(
        assignee_summary,
        use_container_width=True,
        hide_index=True
    )

    top_assignee = assignee_summary.iloc[0]["Assignee"]
    top_count = assignee_summary.iloc[0]["Open_Tickets"]
    top_overdue = assignee_summary.iloc[0]["Overdue_1_Month"]

    st.subheader("📍 Assignee Interpretation")

    st.info(
        f"""
        **{top_assignee}** currently has the highest open workload with 
        **{top_count} active tickets**, including **{top_overdue} tickets older than one month**.  
        This view helps identify workload imbalance, aging backlog concentration, and tickets that may need reassignment or escalation.
        """
    )