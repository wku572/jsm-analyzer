import math
import pandas as pd
import streamlit as st
from supabase import create_client


CURRENT_TABLE = "current_snapshot"
HISTORY_TABLE = "historical_snapshots"


def get_client():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_role_key"]
    return create_client(url, key)


def make_json_safe_value(value):
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    return value


def clean_dataframe_for_json(df):
    clean_df = df.copy()

    for col in clean_df.columns:
        if pd.api.types.is_datetime64_any_dtype(clean_df[col]):
            clean_df[col] = clean_df[col].astype(str)

    records = clean_df.to_dict(orient="records")

    safe_records = []

    for record in records:
        safe_record = {
            key: make_json_safe_value(value)
            for key, value in record.items()
        }
        safe_records.append(safe_record)

    return safe_records


def save_current_snapshot(df):
    client = get_client()

    records = clean_dataframe_for_json(df)

    client.table(CURRENT_TABLE).delete().neq("id", 0).execute()

    if records:
        payload = [{"data": record} for record in records]
        client.table(CURRENT_TABLE).insert(payload).execute()


def load_current_snapshot():
    client = get_client()

    all_rows = []
    batch_size = 1000
    start = 0

    while True:
        end = start + batch_size - 1

        response = (
            client.table(CURRENT_TABLE)
            .select("data")
            .range(start, end)
            .execute()
        )

        rows = response.data

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < batch_size:
            break

        start += batch_size

    if not all_rows:
        return None

    records = [row["data"] for row in all_rows]

    return pd.DataFrame(records)


def save_historical_snapshot(df):
    client = get_client()

    clean_df = df.copy()

    if clean_df.empty:
        return

    total_tickets = len(clean_df)
    in_progress = len(clean_df[clean_df["Status Category"] == "In Progress"])
    pending = len(clean_df[clean_df["Status Category"] == "Pending"])
    resolved = len(clean_df[clean_df["Status Category"] == "Resolved"])

    active_df = clean_df[
        clean_df["Status Category"].isin(["In Progress", "Pending"])
    ]

    overdue_1_month = len(active_df[active_df["Ticket Age"] > 30])
    overdue_2_months = len(active_df[active_df["Ticket Age"] > 60])

    high_priority_open = len(
        active_df[
            active_df["Priority"].isin(["High", "Highest", "Critical"])
        ]
    )

    unassigned_open = len(
        active_df[
            active_df["Assignee"].fillna("").str.lower().isin(["", "unassigned"])
        ]
    )

    organization_summary = (
        clean_df.groupby("Organizations")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .to_dict()
    )

    assignee_summary = (
        active_df.groupby("Assignee")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .to_dict()
    )

    issue_type_summary = (
        clean_df.groupby("Issue Type")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .to_dict()
    )

    payload = {
        "total_tickets": int(total_tickets),
        "in_progress": int(in_progress),
        "pending": int(pending),
        "resolved": int(resolved),
        "active_backlog": int(in_progress + pending),
        "overdue_1_month": int(overdue_1_month),
        "overdue_2_months": int(overdue_2_months),
        "high_priority_open": int(high_priority_open),
        "unassigned_open": int(unassigned_open),
        "organization_summary": organization_summary,
        "assignee_summary": assignee_summary,
        "issue_type_summary": issue_type_summary
    }

    client.table(HISTORY_TABLE).insert(payload).execute()

def load_historical_snapshots():
    client = get_client()

    response = (
        client.table(HISTORY_TABLE)
        .select("*")
        .order("snapshot_timestamp", desc=False)
        .execute()
    )

    rows = response.data

    if not rows:
        return None

    return pd.DataFrame(rows)

def clear_current_snapshot():
    client = get_client()
    client.table(CURRENT_TABLE).delete().neq("id", 0).execute()