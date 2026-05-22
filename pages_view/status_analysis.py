import streamlit as st
import plotly.express as px


def render(filtered_df):

    st.subheader("📊 Status & Queue Health")

    status_summary = filtered_df["Status Category"].value_counts().reset_index()
    status_summary.columns = ["Status Category", "Ticket Count"]

    fig = px.bar(
        status_summary,
        x="Status Category",
        y="Ticket Count",
        text="Ticket Count",
        title="Tickets by Official Status Category"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    status_detail = filtered_df.groupby(
        ["Status Category", "Status"]
    ).size().reset_index(name="Ticket Count")

    fig2 = px.bar(
        status_detail,
        x="Status Category",
        y="Ticket Count",
        color="Status",
        text="Ticket Count",
        barmode="stack",
        title="Raw Jira Status Grouped Under Official Category"
    )
    fig2.update_traces(textposition="inside")
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📋 Status Breakdown Table")
    st.dataframe(status_detail, use_container_width=True, hide_index=True)

    in_progress = len(filtered_df[filtered_df["Status Category"] == "In Progress"])
    pending = len(filtered_df[filtered_df["Status Category"] == "Pending"])
    resolved = len(filtered_df[filtered_df["Status Category"] == "Resolved"])

    st.subheader("📍 Queue Health Interpretation")

    st.info(
        f"""
        The queue currently contains **{in_progress} In Progress**, 
        **{pending} Pending**, and **{resolved} Resolved** tickets.  
        Raw Jira statuses are grouped under the official reporting categories, 
        so operational reporting remains consistent even if Jira has many workflow statuses.
        """
    )