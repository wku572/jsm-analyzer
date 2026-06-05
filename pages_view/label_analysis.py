import streamlit as st
import pandas as pd
import plotly.express as px

from utils.ui import kpi_card


PRIMARY = "#0B4F63"
ACCENT = "#F28C28"
SUCCESS = "#22C55E"
WARNING = "#EF4444"

STATUS_COLORS = {
    "In Progress": PRIMARY,
    "Pending": ACCENT,
    "Resolved": SUCCESS
}

LABEL_COLORS = PRIMARY

def expand_labels(df):
    df = df.copy()

    if "Labels" not in df.columns:
        df["Labels"] = "Unlabeled"

    df["Labels"] = df["Labels"].fillna("Unlabeled").astype(str)

    df["Label List"] = df["Labels"].apply(
        lambda x: [
            label.strip()
            for label in x.split(",")
            if label.strip()
        ]
        if x and x.lower() != "nan"
        else ["Unlabeled"]
    )

    return (
        df.explode("Label List")
        .rename(columns={"Label List": "Issue Category"})
    )


def render(filtered_df):
    st.subheader("🏷️ Label / Category Analysis")

    if filtered_df.empty:
        st.info("No tickets found for the selected filters.")
        return

    label_df = expand_labels(filtered_df)

    total_tickets = len(filtered_df)

    labeled_tickets = len(
        filtered_df[
            filtered_df["Labels"]
            .fillna("Unlabeled")
            .astype(str)
            .str.strip()
            .ne("Unlabeled")
        ]
    )

    unlabeled_tickets = total_tickets - labeled_tickets

    coverage = (
        round((labeled_tickets / total_tickets) * 100, 1)
        if total_tickets
        else 0
    )

    unique_categories = label_df["Issue Category"].nunique()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi_card(
            "Total Tickets",
            total_tickets,
            "Filtered ticket count",
            "📦"
        )

    with c2:
        kpi_card(
            "Labeled Tickets",
            labeled_tickets,
            "Tickets with Jira labels",
            "🏷️"
        )

    with c3:
        kpi_card(
            "Unlabeled Tickets",
            unlabeled_tickets,
            "Need category labeling",
            "⚠️"
        )

    with c4:
        kpi_card(
            "Label Coverage",
            f"{coverage}%",
            f"{unique_categories} total categories",
            "📈"
        )

    st.divider()

    st.subheader("📊 Top Issue Categories")

    category_summary = (
        label_df.groupby("Issue Category")
        .size()
        .reset_index(name="Ticket Count")
        .sort_values("Ticket Count", ascending=False)
        .head(15)
    )

    fig = px.bar(
        category_summary,
        x="Issue Category",
        y="Ticket Count",
        text="Ticket Count",
        title="Most Common Issue Categories",
        color_discrete_sequence=[LABEL_COLORS]
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=460,
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig, width="stretch")

    st.subheader("📌 Issue Categories by Status")

    status_category_summary = (
        label_df.groupby(["Issue Category", "Status Category"])
        .size()
        .reset_index(name="Ticket Count")
    )

    top_categories = category_summary["Issue Category"].tolist()

    status_category_summary = status_category_summary[
        status_category_summary["Issue Category"].isin(top_categories)
    ]

    fig2 = px.bar(
        status_category_summary,
        x="Issue Category",
        y="Ticket Count",
        color="Status Category",
        text="Ticket Count",
        barmode="group",
        title="Issue Categories by Status",
        color_discrete_map=STATUS_COLORS
    )

    fig2.update_traces(textposition="outside")
    fig2.update_layout(
        height=500,
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig2, width="stretch")

    st.subheader("🏦 Issue Categories by Organization")

    org_category_summary = (
        label_df.groupby(["Organizations", "Issue Category"])
        .size()
        .reset_index(name="Ticket Count")
    )

    top_orgs = (
        filtered_df.groupby("Organizations")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .index
        .tolist()
    )

    org_category_summary = org_category_summary[
        org_category_summary["Organizations"].isin(top_orgs)
    ]

    fig3 = px.bar(
        org_category_summary,
        x="Organizations",
        y="Ticket Count",
        color="Issue Category",
        text="Ticket Count",
        title="Top Organizations by Issue Category",
        barmode="stack"
    )

    fig3.update_layout(
        height=520,
        xaxis_tickangle=-35
    )

    st.plotly_chart(fig3, width="stretch")

    st.subheader("📋 Category Summary Table")

    table = (
        label_df.pivot_table(
            index="Issue Category",
            columns="Status Category",
            values="Key",
            aggfunc="count",
            fill_value=0
        )
        .reset_index()
    )

    for col in ["In Progress", "Pending", "Resolved"]:
        if col not in table.columns:
            table[col] = 0

    table["Total"] = (
        table["In Progress"] +
        table["Pending"] +
        table["Resolved"]
    )

    table = table.sort_values("Total", ascending=False)

    st.dataframe(
        table[
            [
                "Issue Category",
                "In Progress",
                "Pending",
                "Resolved",
                "Total"
            ]
        ],
        width="stretch",
        hide_index=True
    )

    st.subheader("💡 Label Intelligence Summary")

    labeled_only = table[
        table["Issue Category"] != "Unlabeled"
    ]

    if not labeled_only.empty:
        top_labeled = labeled_only.iloc[0]
        top_labeled_text = (
            f"The most common labeled issue category is "
            f"**{top_labeled['Issue Category']}** with "
            f"**{top_labeled['Total']} tickets**."
        )
    else:
        top_labeled_text = (
            "No meaningful labeled category has been established yet."
        )

    st.info(
        f"""
        **{unlabeled_tickets} tickets are currently unlabeled**, meaning the current label coverage rate is **{coverage}%**.

        {top_labeled_text}

        This page should be used as both a **category intelligence view** and a **labeling adoption monitor**. 
        Support teams should continue labeling tickets using common issue categories such as 
        **reconciliation, scoring, disbursement, repayment, OVP, KYC, ledger, security, collection, and integration**.

        As labeling improves, this page will become more valuable for identifying recurring support themes, root-cause patterns, and organization-specific issue concentrations.
        """
    )