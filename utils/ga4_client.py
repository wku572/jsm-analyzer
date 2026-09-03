import datetime

import streamlit as st
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)


_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_ga4_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError(
            "GA4 service account credentials are not configured. "
            "Add a [gcp_service_account] section to secrets.toml."
        )

    info = dict(st.secrets["gcp_service_account"])
    credentials = service_account.Credentials.from_service_account_info(
        info,
        scopes=_SCOPES,
    )
    return BetaAnalyticsDataClient(credentials=credentials)


def fetch_ga4_daily_active_users(property_id, start_date="90daysAgo", end_date="yesterday"):
    if not str(property_id).strip():
        raise ValueError("A GA4 property ID is required.")

    client = _get_ga4_client()

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
    )

    response = client.run_report(request)

    rows = []
    for row in response.rows:
        date_text = row.dimension_values[0].value
        active_users_text = row.metric_values[0].value

        activity_date = datetime.datetime.strptime(date_text, "%Y%m%d").date()

        rows.append({
            "activity_date": activity_date,
            "active_users": float(active_users_text),
        })

    return rows
