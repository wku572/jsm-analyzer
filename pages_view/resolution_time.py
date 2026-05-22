import streamlit as st
import plotly.express as px


def resolution_kpi_card(title, value, note, border_color):

    st.markdown(
        f"""
        <div style="
            background:#111827;
            padding:18px;
            border-radius:14px;
            border-left:6px solid {border_color};
            box-shadow:0 8px 22px rgba(0,0,0,0.18);
            margin-bottom:15px;
        ">
            <div style="font-size:14px;color:#9ca3af;font-weight:600;">
                {title}
            </div>
            <div style="font-size:34px;font-weight:800;color:white;margin-top:6px;">
                {value}
            </div>
            <div style="font-size:12px;color:#9ca3af;margin-top:5px;">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render(filtered_df):

    st.subheader("⏱️ Average Ticket Resolution Time")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    resolved_df = filtered_df[
        (filtered_df["Status Category"] == "Resolved") &
        (filtered_df["Resolution Time Days"].notna())
    ].copy()

    resolved_df = resolved_df[
        (resolved_df["Resolution Time Days"] >= 0.01) &
        (resolved_df["Resolution Time Days"] <= 365)
    ]

    if resolved_df.empty:
        st.warning("No resolved tickets with valid resolution time found.")
        return

    avg_resolution = round(resolved_df["Resolution Time Days"].mean(), 2)
    median_resolution = round(resolved_df["Resolution Time Days"].median(), 2)
    fastest_resolution = round(resolved_df["Resolution Time Days"].min(), 2)
    slowest_resolution = round(resolved_df["Resolution Time Days"].max(), 2)

    st.subheader("⏱️ Resolution Time Overview")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        resolution_kpi_card(
            "Average Resolution",
            f"{avg_resolution} days",
            "Overall average completion time",
            "#3b82f6"
        )

    with c2:
        resolution_kpi_card(
            "Median Resolution",
            f"{median_resolution} days",
            "Typical ticket completion time",
            "#10b981"
        )

    with c3:
        resolution_kpi_card(
            "Fastest Resolution",
            f"{fastest_resolution} days",
            "Shortest completed ticket",
            "#f59e0b"
        )

    with c4:
        resolution_kpi_card(
            "Slowest Resolution",
            f"{slowest_resolution} days",
            "Longest completed ticket",
            "#ef4444"
        )

    st.divider()

    st.subheader("📊 Resolution Time by Issue Type")

    issue_resolution = resolved_df.groupby("Issue Type").agg(
        Resolved_Tickets=("Key", "count"),
        Avg_Resolution_Days=("Resolution Time Days", "mean"),
        Median_Resolution_Days=("Resolution Time Days", "median"),
        Max_Resolution_Days=("Resolution Time Days", "max")
    ).reset_index()

    issue_resolution = issue_resolution.round(2)
    issue_resolution = issue_resolution.sort_values(
        "Avg_Resolution_Days",
        ascending=False
    )

    fig = px.bar(
        issue_resolution,
        x="Issue Type",
        y="Avg_Resolution_Days",
        text="Avg_Resolution_Days",
        title="Average Resolution Time by Issue Type"
    )

    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        issue_resolution,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("👤 Resolution Time by Assignee")

    assignee_resolution = resolved_df.groupby("Assignee").agg(
        Resolved_Tickets=("Key", "count"),
        Avg_Resolution_Days=("Resolution Time Days", "mean"),
        Median_Resolution_Days=("Resolution Time Days", "median"),
        Max_Resolution_Days=("Resolution Time Days", "max")
    ).reset_index()

    assignee_resolution = assignee_resolution.round(2)
    assignee_resolution = assignee_resolution.sort_values(
        "Avg_Resolution_Days",
        ascending=False
    )

    fig2 = px.bar(
        assignee_resolution,
        x="Assignee",
        y="Avg_Resolution_Days",
        text="Avg_Resolution_Days",
        title="Average Resolution Time by Assignee"
    )

    fig2.update_layout(xaxis_tickangle=-45)
    fig2.update_traces(textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(
        assignee_resolution,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🏦 Resolution Time by Organization")

    org_resolution = resolved_df.groupby("Organizations").agg(
        Resolved_Tickets=("Key", "count"),
        Avg_Resolution_Days=("Resolution Time Days", "mean"),
        Median_Resolution_Days=("Resolution Time Days", "median"),
        Max_Resolution_Days=("Resolution Time Days", "max")
    ).reset_index()

    org_resolution = org_resolution.round(2)
    org_resolution = org_resolution.sort_values(
        "Avg_Resolution_Days",
        ascending=False
    )

    fig3 = px.bar(
        org_resolution,
        x="Organizations",
        y="Avg_Resolution_Days",
        text="Avg_Resolution_Days",
        title="Average Resolution Time by Organization"
    )

    fig3.update_layout(xaxis_tickangle=-45)
    fig3.update_traces(textposition="outside")
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(
        org_resolution,
        use_container_width=True,
        hide_index=True
    )

    slowest_issue = issue_resolution.iloc[0]["Issue Type"]
    slowest_issue_avg = issue_resolution.iloc[0]["Avg_Resolution_Days"]

    slowest_assignee = assignee_resolution.iloc[0]["Assignee"]
    slowest_assignee_avg = assignee_resolution.iloc[0]["Avg_Resolution_Days"]

    resolution_gap = round(avg_resolution - median_resolution, 2)

    st.subheader("📍 Resolution Time Interpretation")

    st.warning(
        f"""
        The overall average ticket resolution time is **{avg_resolution} days**, 
        while the median resolution time is **{median_resolution} days**.

        The gap between average and median is **{resolution_gap} days**, which suggests that 
        a subset of long-running tickets is increasing the overall resolution time.

        The slowest issue category is **{slowest_issue}** with an average resolution time of 
        **{slowest_issue_avg} days**.

        The assignee with the highest average resolution time is **{slowest_assignee}** 
        at **{slowest_assignee_avg} days**.

        Long resolution time does not automatically indicate poor performance. 
        It may also reflect customer-side delays, bank confirmation dependency, engineering backlog, 
        unclear requirements, recurring defects, or third-party integration delays.
        """
    )