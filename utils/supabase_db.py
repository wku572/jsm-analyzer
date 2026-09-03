import math
import pandas as pd
import streamlit as st
from supabase import create_client


CURRENT_TABLE = "current_snapshot"
HISTORY_TABLE = "historical_snapshots"
INCIDENT_IMPACT_TABLE = "incident_impact_assessments"
GA4_ACTIVITY_TABLE = "ga4_activity"
GA4_PROPERTY_MAP_TABLE = "ga4_property_map"
TICKET_EMBEDDINGS_TABLE = "ticket_embeddings"
TICKET_EMBEDDINGS_BATCH_SIZE = 200


def _is_missing_table_error(exc):
    message = str(exc)
    return "PGRST205" in message or "Could not find the table" in message


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


def save_incident_impact_assessment(payload):
    client = get_client()
    response = client.table(INCIDENT_IMPACT_TABLE).insert(payload).execute()

    rows = response.data
    return rows[0].get("id") if rows else None


def update_incident_impact_assessment(record_id, payload):
    client = get_client()
    client.table(INCIDENT_IMPACT_TABLE).update(payload).eq("id", record_id).execute()


def delete_incident_impact_assessment(record_id):
    client = get_client()
    client.table(INCIDENT_IMPACT_TABLE).delete().eq("id", record_id).execute()


def load_incident_impact_assessments():
    client = get_client()

    response = (
        client.table(INCIDENT_IMPACT_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    rows = response.data

    if not rows:
        return None

    return pd.DataFrame(rows)


def _ga4_normalize_activity_frame(records):
    if isinstance(records, pd.DataFrame):
        df = records.copy()
    else:
        df = pd.DataFrame(records)

    if df.empty:
        return df

    rename_map = {
        "organization": "organization",
        "activity_date": "activity_date",
        "weekday": "weekday",
        "hour": "hour",
        "active_users": "active_users",
        "source": "source",
        "excluded": "excluded",
        "notes": "notes",
    }

    df = df.rename(columns=rename_map)

    required_defaults = {
        "organization": "",
        "activity_date": pd.NaT,
        "weekday": "",
        "hour": pd.NA,
        "active_users": 0,
        "source": "GA4",
        "excluded": False,
        "notes": "",
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    df["organization"] = df["organization"].fillna("").astype(str).str.strip()
    df["activity_date"] = pd.to_datetime(df["activity_date"], errors="coerce").dt.date
    df["weekday"] = df["weekday"].fillna("").astype(str).str.strip()
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df["active_users"] = pd.to_numeric(df["active_users"], errors="coerce").fillna(0).astype(float)
    df["source"] = df["source"].fillna("GA4").astype(str).str.strip()
    df["excluded"] = df["excluded"].fillna(False).astype(bool)
    df["notes"] = df["notes"].fillna("").astype(str)

    df = df[df["organization"].ne("")]
    df = df[df["activity_date"].notna()]
    df = df[df["weekday"].ne("")]

    return df


def save_ga4_activity_records(records):
    client = get_client()
    df = _ga4_normalize_activity_frame(records)

    if df.empty:
        return

    payload = []
    for _, row in df.iterrows():
        payload.append({
            "organization": row["organization"],
            "activity_date": row["activity_date"].isoformat() if hasattr(row["activity_date"], "isoformat") else str(row["activity_date"]),
            "weekday": row["weekday"],
            "hour": None if pd.isna(row["hour"]) else int(row["hour"]),
            "active_users": float(row["active_users"]),
            "source": row["source"],
            "excluded": bool(row["excluded"]),
            "notes": row["notes"],
        })

    try:
        client.table(GA4_ACTIVITY_TABLE).upsert(
            payload,
            on_conflict="organization,activity_date,source"
        ).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise RuntimeError(
                "The ga4_activity table does not exist yet. Run the Phase 2 SQL script before using GA4 features."
            ) from exc
        raise


def load_ga4_activity_records():
    client = get_client()

    try:
        response = (
            client.table(GA4_ACTIVITY_TABLE)
            .select("*")
            .order("activity_date", desc=False)
            .execute()
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise

    rows = response.data

    if not rows:
        return None

    df = pd.DataFrame(rows)
    if "activity_date" in df.columns:
        df["activity_date"] = pd.to_datetime(df["activity_date"], errors="coerce")

    return df


def load_ga4_baseline_records(organization, weekday, incident_date=None, lookback=8):
    df = load_ga4_activity_records()

    if df is None or df.empty:
        return None

    baseline_df = df.copy()
    baseline_df = baseline_df[
        baseline_df["organization"].fillna("").astype(str).str.strip().str.casefold()
        == str(organization).strip().casefold()
    ]
    baseline_df = baseline_df[
        baseline_df["weekday"].fillna("").astype(str).str.strip().str.casefold()
        == str(weekday).strip().casefold()
    ]

    if "excluded" in baseline_df.columns:
        baseline_df = baseline_df[~baseline_df["excluded"].fillna(False)]

    if incident_date is not None:
        incident_date = pd.to_datetime(incident_date, errors="coerce")
        if pd.notna(incident_date) and "activity_date" in baseline_df.columns:
            baseline_dates = pd.to_datetime(
                baseline_df["activity_date"],
                errors="coerce"
            ).dt.date
            cutoff_date = incident_date.date()
            baseline_df = baseline_df[baseline_dates < cutoff_date]

    if baseline_df.empty:
        return None

    if "activity_date" in baseline_df.columns:
        baseline_df = baseline_df.sort_values("activity_date", ascending=False)

    baseline_df = baseline_df.head(lookback).copy()
    return baseline_df


def calculate_ga4_weekday_baseline(organization, weekday, incident_date=None, lookback=8):
    baseline_df = load_ga4_baseline_records(
        organization,
        weekday,
        incident_date=incident_date,
        lookback=lookback
    )

    if baseline_df is None or baseline_df.empty:
        return None

    active_users = pd.to_numeric(
        baseline_df["active_users"],
        errors="coerce"
    ).dropna()

    if active_users.empty:
        return None

    expected_users = round(float(active_users.mean()), 2)

    return {
        "expected_users": expected_users,
        "lookback_used": int(len(baseline_df)),
        "records": baseline_df,
        "baseline_type": "GA4 Same-Weekday Phase 2",
    }


def calculate_ga4_rolling_mau_baseline(organization, incident_date=None, lookback_days=30):
    df = load_ga4_activity_records()

    if df is None or df.empty:
        return None

    baseline_df = df.copy()
    baseline_df = baseline_df[
        baseline_df["organization"].fillna("").astype(str).str.strip().str.casefold()
        == str(organization).strip().casefold()
    ]

    if "excluded" in baseline_df.columns:
        baseline_df = baseline_df[~baseline_df["excluded"].fillna(False)]

    if incident_date is not None and "activity_date" in baseline_df.columns:
        incident_date = pd.to_datetime(incident_date, errors="coerce")
        if pd.notna(incident_date):
            baseline_dates = pd.to_datetime(
                baseline_df["activity_date"],
                errors="coerce",
            ).dt.date
            start_window = (incident_date - pd.Timedelta(days=lookback_days)).date()
            cutoff_date = incident_date.date()
            baseline_df = baseline_df[
                (baseline_dates >= start_window) &
                (baseline_dates < cutoff_date)
            ]

    if baseline_df.empty:
        return None

    if "activity_date" in baseline_df.columns:
        baseline_df = baseline_df.sort_values("activity_date", ascending=False)

    active_users = pd.to_numeric(
        baseline_df["active_users"],
        errors="coerce"
    ).dropna()

    if active_users.empty:
        return None

    expected_users = round(float(active_users.mean()), 2)

    return {
        "expected_users": expected_users,
        "lookback_used": int(len(baseline_df)),
        "records": baseline_df.head(lookback_days).copy(),
        "baseline_type": "GA4 Rolling 30-Day MAU Phase 2",
    }


def load_ga4_property_map():
    client = get_client()

    try:
        response = (
            client.table(GA4_PROPERTY_MAP_TABLE)
            .select("organization, property_id")
            .execute()
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            return {}
        raise

    rows = response.data

    if not rows:
        return {}

    return {
        row["organization"]: row["property_id"]
        for row in rows
        if row.get("organization")
    }


def save_ga4_property_mapping(organization, property_id):
    client = get_client()

    organization = str(organization).strip()
    property_id = str(property_id).strip()

    try:
        client.table(GA4_PROPERTY_MAP_TABLE).upsert(
            {"organization": organization, "property_id": property_id},
            on_conflict="organization"
        ).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise RuntimeError(
                "The ga4_property_map table does not exist yet. "
                "Create it before mapping organizations to GA4 properties."
            ) from exc
        raise


def delete_ga4_property_mapping(organization):
    client = get_client()
    client.table(GA4_PROPERTY_MAP_TABLE).delete().eq(
        "organization", str(organization).strip()
    ).execute()


def _format_pgvector(values):
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def save_ticket_embeddings(rows):
    if not rows:
        return

    client = get_client()

    payload = [
        {
            "ticket_id": row["ticket_id"],
            "escalation_level": row["escalation_level"],
            "document": row["document"],
            "embedding": _format_pgvector(row["embedding"]),
        }
        for row in rows
    ]

    try:
        for start in range(0, len(payload), TICKET_EMBEDDINGS_BATCH_SIZE):
            batch = payload[start:start + TICKET_EMBEDDINGS_BATCH_SIZE]
            client.table(TICKET_EMBEDDINGS_TABLE).upsert(
                batch,
                on_conflict="ticket_id"
            ).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise RuntimeError(
                "The ticket_embeddings table does not exist yet. "
                "Run the pgvector migration before using Support Triage."
            ) from exc
        raise


def match_ticket_embeddings(query_embedding, match_count=5):
    client = get_client()

    try:
        response = client.rpc(
            "match_ticket_embeddings",
            {
                "query_embedding": _format_pgvector(query_embedding),
                "match_count": match_count,
            }
        ).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise RuntimeError(
                "The ticket_embeddings table does not exist yet. "
                "Run the pgvector migration before using Support Triage."
            ) from exc
        raise

    return response.data or []


def get_ticket_embeddings_count():
    client = get_client()

    try:
        response = (
            client.table(TICKET_EMBEDDINGS_TABLE)
            .select("ticket_id", count="exact", head=True)
            .execute()
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            return 0
        raise

    return response.count or 0
