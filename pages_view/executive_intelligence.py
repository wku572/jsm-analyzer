import streamlit as st
import plotly.express as px


# Brand colors
PRIMARY = "#0B4F63"     # Kifiya dark teal
ACCENT = "#F28C28"      # orange
SUCCESS = "#22C55E"     # green

STATUS_COLORS = PRIMARY

def calculate_queue_health(df):
    active_df = df[df["Status Category"] != "Resolved"]

    active_total = len(active_df)
    if active_total == 0:
        return 100, "Healthy", "#16a34a"

    pending = len(active_df[active_df["Status Category"] == "Pending"])
    overdue_1m = len(active_df[active_df["Ticket Age"] > 30])
    overdue_2m = len(active_df[active_df["Ticket Age"] > 60])

    high_priority_open = len(
        active_df[active_df["Priority"].isin(["Highest", "High"])]
    )

    pending_rate = pending / active_total
    overdue_1m_rate = overdue_1m / active_total
    overdue_2m_rate = overdue_2m / active_total
    high_priority_rate = high_priority_open / active_total

    score = 100
    score -= pending_rate * 20
    score -= overdue_1m_rate * 25
    score -= overdue_2m_rate * 35
    score -= high_priority_rate * 20

    score = max(0, round(score))

    if score >= 80:
        status = "Healthy"
        color = "#16a34a"
    elif score >= 60:
        status = "Moderate Risk"
        color = "#f59e0b"
    else:
        status = "Critical"
        color = "#dc2626"

    return score, status, color


def insight_card(title, value, note, color):
    st.markdown(
        f"""
        <div style="
            background:white;
            border-radius:18px;
            padding:20px;
            border-left:6px solid {color};
            box-shadow:0 8px 24px rgba(15,23,42,0.06);
            min-height:130px;
        ">
            <div style="
                color:#64748b;
                font-size:12px;
                font-weight:800;
                text-transform:uppercase;
                letter-spacing:0.5px;
            ">
                {title}
            </div>
            <div style="
                color:{PRIMARY};
                font-size:36px;
                font-weight:900;
                margin-top:8px;
            ">
                {value}
            </div>
            <div style="
                color:#64748b;
                font-size:12px;
                margin-top:8px;
                line-height:1.4;
            ">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def alert_box(message, severity="warning"):
    if severity == "critical":
        color = "#dc2626"
        bg = "#fef2f2"
        icon = "🚨"
    elif severity == "warning":
        color = "#f59e0b"
        bg = "#fffbeb"
        icon = "⚠️"
    else:
        color = "#2563eb"
        bg = "#eff6ff"
        icon = "ℹ️"

    st.markdown(
        f"""
        <div style="
            background:{bg};
            border-left:5px solid {color};
            padding:14px 16px;
            border-radius:12px;
            margin-bottom:10px;
            color:#334155;
            font-weight:600;
        ">
            {icon} {message}
        </div>
        """,
        unsafe_allow_html=True
    )


def generate_alerts(df):
    alerts = []

    active_df = df[df["Status Category"] != "Resolved"]

    high_priority_old = len(
        active_df[
            (active_df["Priority"].isin(["Highest", "High"])) &
            (active_df["Ticket Age"] > 30)
        ]
    )

    if high_priority_old > 0:
        alerts.append(
            (
                f"{high_priority_old} high-priority tickets are older than 30 days.",
                "critical"
            )
        )

    pending = len(active_df[active_df["Status Category"] == "Pending"])

    if pending > 50:
        alerts.append(
            (
                f"Pending queue is high with {pending} tickets waiting for action.",
                "warning"
            )
        )

    assignee_load = (
        active_df.groupby("Assignee")
        .size()
        .reset_index(name="Active_Tickets")
    )

    overloaded = assignee_load[assignee_load["Active_Tickets"] > 20]

    if len(overloaded) > 0:
        alerts.append(
            (
                f"{len(overloaded)} assignees currently have more than 20 active tickets.",
                "warning"
            )
        )

    aging = len(active_df[active_df["Ticket Age"] > 60])

    if aging > 20:
        alerts.append(
            (
                f"Severe aging backlog detected with {aging} open tickets older than 60 days.",
                "critical"
            )
        )

    return alerts


def render(df):
    st.markdown("## 🧠 Executive Intelligence")

    if df.empty:
        st.info("No data available for executive intelligence.")
        return

    active_df = df[df["Status Category"] != "Resolved"]

    score, status, color = calculate_queue_health(df)

    total = len(df)
    active_total = len(active_df)
    pending = len(active_df[active_df["Status Category"] == "Pending"])
    overdue_1m = len(active_df[active_df["Ticket Age"] > 30])
    overdue_2m = len(active_df[active_df["Ticket Age"] > 60])
    high_priority_open = len(
        active_df[active_df["Priority"].isin(["Highest", "High"])]
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        insight_card(
            "Queue Health Score",
            f"{score}/100",
            f"Overall queue status: {status}",
            color
        )

    with c2:
        insight_card(
            "Active Tickets",
            active_total,
            "In Progress + Pending workload",
            ACCENT
        )

    with c3:
        insight_card(
            "Overdue > 1 Month",
            overdue_1m,
            "Open tickets older than 30 days",
            "#dc2626"
        )

    with c4:
        insight_card(
            "High Priority Open",
            high_priority_open,
            "High/Highest unresolved tickets",
            "#7c3aed"
        )

    st.markdown(
        f"""
        <div style="
            margin-top:18px;
            margin-bottom:24px;
            padding:18px 20px;
            border-radius:16px;
            background:#f8fafc;
            border:1px solid #e2e8f0;
        ">
            <div style="font-size:18px;font-weight:800;color:{PRIMARY};">
                Operational State: 
                <span style="color:{color};">{status}</span>
            </div>
            <div style="color:#64748b;font-size:13px;margin-top:6px;line-height:1.5;">
                The score is calculated from active backlog, pending queue pressure, overdue tickets, 
                severe aging, and high-priority unresolved tickets. A lower score indicates higher operational risk.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### 🚨 Operational Alerts")

    alerts = generate_alerts(df)

    if alerts:
        for message, severity in alerts:
            alert_box(message, severity)
    else:
        alert_box("No major operational risks detected.", "info")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown("### 🏦 Top Backlog Organizations")

        org_backlog = (
            active_df.groupby("Organizations")
            .size()
            .reset_index(name="Open_Tickets")
            .sort_values("Open_Tickets", ascending=False)
            .head(10)
        )

        fig = px.bar(
            org_backlog,
            x="Organizations",
            y="Open_Tickets",
            text="Open_Tickets",
            title="Top Organizations by Active Backlog",
            color_discrete_sequence=[STATUS_COLORS]
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=420,
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=50, b=100)
        )

        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### 👨‍💻 Assignee Workload Risk")

        assignee_load = (
            active_df.groupby("Assignee")
            .size()
            .reset_index(name="Active_Tickets")
            .sort_values("Active_Tickets", ascending=False)
            .head(10)
        )

        fig2 = px.bar(
            assignee_load,
            x="Assignee",
            y="Active_Tickets",
            text="Active_Tickets",
            title="Top Assignees by Active Workload",
            color_discrete_sequence=[STATUS_COLORS]
        )

        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            height=420,
            xaxis_tickangle=-35,
            margin=dict(l=20, r=20, t=50, b=100)
        )

        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    st.markdown("### 💡 Executive Summary")

    resolved = len(df[df["Status Category"] == "Resolved"])
    in_progress = len(df[df["Status Category"] == "In Progress"])

    st.info(
        f"""
        The queue currently contains **{in_progress} In Progress**, **{pending} Pending**, 
        and **{resolved} Resolved** tickets from **{total} total tickets**.

        The current Queue Health Score is **{score}/100**, which indicates a **{status}** operational state.

        There are **{overdue_1m} open tickets older than one month** and 
        **{overdue_2m} open tickets older than two months**. These tickets represent the highest backlog risk.

        Organizations with concentrated active backlog should be reviewed for recurring operational bottlenecks, 
        while assignees with heavy active workloads may require redistribution, escalation, or closer follow-up.
        """
    )