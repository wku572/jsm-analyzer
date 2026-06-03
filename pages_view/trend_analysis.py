import streamlit as st
import plotly.express as px
import pandas as pd

PRIMARY = "#0B4F63"
ACCENT = "#F28C28"
SUCCESS = "#22C55E"

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

STATUS_ORDER = ["In Progress", "Pending", "Resolved"]
LOCAL_TZ = "Africa/Addis_Ababa"


def prepare_status_columns(summary_df):
    for col in STATUS_ORDER:
        if col not in summary_df.columns:
            summary_df[col] = 0

    summary_df["Total"] = (
        summary_df["In Progress"] +
        summary_df["Pending"] +
        summary_df["Resolved"]
    )

    return summary_df


def complete_trend_periods(trend_summary, periods):
    full_index = pd.MultiIndex.from_product(
        [periods, STATUS_ORDER],
        names=["Trend Period", "Status Category"]
    )

    trend_summary = (
        trend_summary
        .set_index(["Trend Period", "Status Category"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    return trend_summary


def render(filtered_df):

    st.subheader("📈 Trend Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    df = filtered_df.copy()

    df["Created"] = pd.to_datetime(df["Created"], errors="coerce", utc=True)
    df = df.dropna(subset=["Created"])

    if df.empty:
        st.info("No valid created dates found.")
        return

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
        title=f"{period_label} Tickets by Status Category",
        color_discrete_map=STATUS_COLORS,
        category_orders={"Status Category": STATUS_ORDER}
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(height=420)
    st.plotly_chart(fig, width="stretch")

    if trend_level in ["Monthly", "Yearly"]:

        st.subheader(f"📈 {trend_level} Movement Over Time")

        trend_summary = (
            df.groupby(["Trend Period", "Status Category"])
            .size()
            .reset_index(name="Ticket Count")
        )

        periods = sorted(df["Trend Period"].dropna().unique())
        trend_summary = complete_trend_periods(trend_summary, periods)

        fig = px.line(
            trend_summary,
            x="Trend Period",
            y="Ticket Count",
            color="Status Category",
            markers=True,
            title=f"{trend_level} Ticket Trend by Status Category",
            color_discrete_map=STATUS_COLORS,
            category_orders={"Status Category": STATUS_ORDER}
        )

        fig.update_layout(
            height=450,
            xaxis_tickangle=-45
        )

        st.plotly_chart(fig, width="stretch")

    st.subheader(f"🏦 {period_label} Organization Analysis")

    org_summary = df.pivot_table(
        index="Organizations",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    org_summary = prepare_status_columns(org_summary)
    org_summary = org_summary.sort_values("Total", ascending=False).head(15)

    fig = px.bar(
        org_summary,
        x="Organizations",
        y=STATUS_ORDER,
        title=f"{period_label} Tickets by Organization",
        barmode="group",
        color_discrete_map=STATUS_COLORS
    )

    fig.update_layout(
        height=480,
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        org_summary[["Organizations", "In Progress", "Pending", "Resolved", "Total"]],
        width="stretch",
        hide_index=True
    )

    st.subheader(f"👤 {period_label} Assignee Analysis")

    assignee_summary = df.pivot_table(
        index="Assignee",
        columns="Status Category",
        values="Key",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    assignee_summary = prepare_status_columns(assignee_summary)
    assignee_summary = assignee_summary.sort_values("Total", ascending=False).head(15)

    fig = px.bar(
        assignee_summary,
        x="Assignee",
        y=STATUS_ORDER,
        title=f"{period_label} Tickets by Assignee",
        barmode="group",
        color_discrete_map=STATUS_COLORS
    )

    fig.update_layout(
        height=480,
        xaxis_tickangle=-45
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        assignee_summary[["Assignee", "In Progress", "Pending", "Resolved", "Total"]],
        width="stretch",
        hide_index=True
    )

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
        width="stretch",
        hide_index=True
    )

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

        Monthly and yearly views help identify ticket movement patterns over time, while today and weekly views help monitor short-term operational pressure.
        """
    )