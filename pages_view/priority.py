import streamlit as st
import plotly.express as px


def render(filtered_df):

    st.subheader("🚨 Priority Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    priority_summary = filtered_df.groupby(
        ["Priority", "Status Category"]
    ).size().reset_index(name="Ticket Count")

    fig = px.bar(
        priority_summary,
        x="Priority",
        y="Ticket Count",
        color="Status Category",
        text="Ticket Count",
        title="Tickets by Priority and Status Category",
        barmode="group"
    )

    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    active_df = filtered_df[
        filtered_df["Status Category"].isin(["In Progress", "Pending"])
    ]

    high_priority_open = active_df[
        active_df["Priority"].isin(["High", "Highest"])
    ].sort_values("Ticket Age", ascending=False)

    st.subheader("🔥 High Priority Open Tickets")

    if high_priority_open.empty:
        st.success("No open High or Highest priority tickets found.")
    else:
        st.dataframe(
            high_priority_open[
                [
                    "Key", "Summary", "Assignee", "Reporter",
                    "Priority", "Status", "Status Category",
                    "Ticket Age", "Ticket Age Duration", "Organizations"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.subheader("📍 Priority Interpretation")

    high_count = len(high_priority_open)
    overdue_high = len(high_priority_open[high_priority_open["Ticket Age"] > 30])

    if high_count > 0:
        st.warning(
            f"""
            There are **{high_count} open High/Highest priority tickets**, 
            including **{overdue_high} older than one month**.  
            These should be reviewed first because high-priority aging usually indicates operational risk or missed escalation.
            """
        )
    else:
        st.info(
            "There are no open High/Highest priority tickets under the selected filters."
        )