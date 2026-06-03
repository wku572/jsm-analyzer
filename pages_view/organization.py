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

    st.subheader("🏦 Organization Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    org_summary = filtered_df.pivot_table(
        index="Organizations",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    for col in ["In Progress", "Pending", "Resolved"]:
        if col not in org_summary.columns:
            org_summary[col] = 0

    org_summary["Open Tickets"] = org_summary["In Progress"] + org_summary["Pending"]

    org_summary["Overdue > 1 Month"] = filtered_df[
        filtered_df["Status Category"].isin(["In Progress", "Pending"])
    ].groupby("Organizations")["Ticket Age"].apply(lambda x: (x > 30).sum()).reindex(
        org_summary["Organizations"]
    ).fillna(0).astype(int).values

    org_summary["Total"] = (
        org_summary["In Progress"] +
        org_summary["Pending"] +
        org_summary["Resolved"]
    )

    org_summary = org_summary.sort_values("Total", ascending=False)

    fig = px.bar(
        org_summary,
        x="Organizations",
        y=["In Progress", "Pending", "Resolved"],
        title="Organization Tickets by Status Category",
        barmode="group",
        color_discrete_map=STATUS_COLORS
    )

    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Organization Summary Table")

    st.dataframe(
        org_summary[
            [
                "Organizations",
                "In Progress",
                "Pending",
                "Resolved",
                "Open Tickets",
                "Overdue > 1 Month",
                "Total"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    top_org = org_summary.iloc[0]["Organizations"]
    top_total = org_summary.iloc[0]["Total"]
    top_open = org_summary.iloc[0]["Open Tickets"]
    top_overdue = org_summary.iloc[0]["Overdue > 1 Month"]

    st.subheader("📍 Organization Interpretation")

    st.info(
        f"""
        **{top_org}** has the highest ticket volume with **{top_total} total tickets**.  
        It currently has **{top_open} open tickets**, including **{top_overdue} tickets older than one month**.  
        This view is useful for identifying partner organizations with high support load, unresolved backlog, or repeated operational pressure.
        """
    )