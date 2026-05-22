import streamlit as st
import plotly.express as px
import pandas as pd


LOCAL_TZ = "Africa/Addis_Ababa"


def prepare_status_columns(summary_df):
    for col in ["In Progress", "Pending", "Resolved"]:
        if col not in summary_df.columns:
            summary_df[col] = 0

    summary_df["Total"] = (
        summary_df["In Progress"] +
        summary_df["Pending"] +
        summary_df["Resolved"]
    )

    return summary_df


def render(filtered_df):

    st.subheader("📈 Trend Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    df = filtered_df.copy()

    df["Created"] = pd.to_datetime(df["Created"], errors="coerce", utc=True)
    df = df.dropna(subset=["Created"])

    df["Created Local"] = df["Created"].dt.tz_convert(LOCAL_TZ)
    df["Created Date"] = df["Created Local"].dt.normalize()

    today = pd.Timestamp.now(tz=LOCAL_TZ).normalize()
    week_start = today - pd.Timedelta(days=today.weekday())
    week_end = week_start + pd.Timedelta(days=6)

    trend_level = st.radio(
        "Select trend level",
        ["Today", "This Week", "Monthly", "Yearly"],
        horizontal=True
    )

    if trend_level == "Today":
        df = df[df["Created Date"] == today]
        period_label = f"Today ({today.date()})"

    elif trend_level == "This Week":
        df = df[
            (df["Created Date"] >= week_start) &
            (df["Created Date"] <= week_end)
        ]
        period_label = f"This Week ({week_start.date()} to {week_end.date()})"

    elif trend_level == "Monthly":
        df["Trend Period"] = df["Created Local"].dt.to_period("M").astype(str)
        period_label = "Monthly"

    else:
        df["Trend Period"] = df["Created Local"].dt.year.astype(str)
        period_label = "Yearly"

    if df.empty:
        st.warning(f"No tickets found for {period_label}.")
        return

    # -------------------------
    # STATUS SUMMARY
    # -------------------------
    st.subheader(f"📊 {period_label} Status Summary")

    status_summary = (
        df.groupby("Status Category")
        .size()
        .reset_index(name="Ticket Count")
    )

    fig = px.bar(
        status_summary,
        x="Status Category",
        y="Ticket Count",
        color="Status Category",
        text="Ticket Count",
        title=f"{period_label} Tickets by Status Category"
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # -------------------------
    # MONTHLY / YEARLY TREND LINE
    # -------------------------
    if trend_level in ["Monthly", "Yearly"]:

        trend_summary = (
            df.groupby(["Trend Period", "Status Category"])
            .size()
            .reset_index(name="Ticket Count")
        )

        fig = px.line(
            trend_summary,
            x="Trend Period",
            y="Ticket Count",
            color="Status Category",
            markers=True,
            title=f"{trend_level} Ticket Trend by Status Category"
        )

        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # -------------------------
    # ORGANIZATION ANALYSIS
    # -------------------------
    st.subheader(f"🏦 {period_label} Organization Analysis")

    org_summary = df.pivot_table(
        index="Organizations",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    org_summary = prepare_status_columns(org_summary)
    org_summary = org_summary.sort_values("Total", ascending=False)

    fig = px.bar(
        org_summary,
        x="Organizations",
        y=["In Progress", "Pending", "Resolved"],
        title=f"{period_label} Tickets by Organization",
        barmode="group"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        org_summary[
            ["Organizations", "In Progress", "Pending", "Resolved", "Total"]
        ],
        use_container_width=True,
        hide_index=True
    )

    # -------------------------
    # ASSIGNEE ANALYSIS
    # -------------------------
    st.subheader(f"👤 {period_label} Assignee Analysis")

    assignee_summary = df.pivot_table(
        index="Assignee",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    assignee_summary = prepare_status_columns(assignee_summary)
    assignee_summary = assignee_summary.sort_values("Total", ascending=False)

    fig = px.bar(
        assignee_summary,
        x="Assignee",
        y=["In Progress", "Pending", "Resolved"],
        title=f"{period_label} Tickets by Assignee",
        barmode="group"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        assignee_summary[
            ["Assignee", "In Progress", "Pending", "Resolved", "Total"]
        ],
        use_container_width=True,
        hide_index=True
    )

    # -------------------------
    # PAGINATED TICKET LIST
    # -------------------------
    st.subheader(f"📄 {period_label} Ticket List")

    ticket_columns = [
        "Key", "Summary", "Assignee", "Reporter",
        "Priority", "Status", "Status Category",
        "Created Local", "Organizations"
    ]

    available_columns = [col for col in ticket_columns if col in df.columns]
    ticket_data = df[available_columns].copy()

    total_rows = len(ticket_data)

    p1, p2, p3 = st.columns(3)

    with p1:
        page_size = st.selectbox(
            "Rows per page",
            [10, 25, 50, 100, 200],
            index=1,
            key=f"{trend_level}_ticket_page_size"
        )

    total_pages = max((total_rows - 1) // page_size + 1, 1)

    with p2:
        page_number = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key=f"{trend_level}_ticket_page_number"
        )

    with p3:
        st.metric("Total Tickets", total_rows)

    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size

    st.caption(
        f"Showing rows {start_idx + 1} to {min(end_idx, total_rows)} of {total_rows}"
    )

    st.dataframe(
        ticket_data.iloc[start_idx:end_idx],
        use_container_width=True,
        hide_index=True
    )

    # -------------------------
    # INTERPRETATION
    # -------------------------
    top_org = org_summary.iloc[0]["Organizations"]
    top_org_total = org_summary.iloc[0]["Total"]

    top_assignee = assignee_summary.iloc[0]["Assignee"]
    top_assignee_total = assignee_summary.iloc[0]["Total"]

    st.subheader("📍 Trend Interpretation")

    st.info(
        f"""
        For **{period_label}**, the highest organization ticket volume is from 
        **{top_org}** with **{top_org_total} tickets**.  
        The highest assignee workload is **{top_assignee}** with 
        **{top_assignee_total} tickets**.  
        This view helps identify short-term workload pressure and long-term ticket movement by organization and owner.
        """
    )