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

    response = client.table(CURRENT_TABLE).select("data").execute()

    rows = response.data

    if not rows:
        return None

    records = [row["data"] for row in rows]

    return pd.DataFrame(records)


def save_historical_snapshot(df):
    client = get_client()

    records = clean_dataframe_for_json(df)

    if records:
        payload = [{"data": record} for record in records]
        client.table(HISTORY_TABLE).insert(payload).execute()


def load_historical_snapshots():
    client = get_client()

    response = client.table(HISTORY_TABLE).select("*").execute()

    rows = response.data

    if not rows:
        return None

    records = []

    for row in rows:
        item = row["data"]
        item["snapshot_timestamp"] = row["snapshot_timestamp"]
        records.append(item)

    return pd.DataFrame(records)


def clear_current_snapshot():
    client = get_client()
    client.table(CURRENT_TABLE).delete().neq("id", 0).execute()