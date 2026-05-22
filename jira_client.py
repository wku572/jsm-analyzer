import requests
import pandas as pd
import streamlit as st
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone


def map_status_category(status):
    resolved_statuses = [
        "Resolved", "Completed", "Closed",
        "Canceled", "Cancelled", "Done"
    ]

    pending_statuses = [
        "Waiting for customer", "Pending"
    ]

    if status in resolved_statuses:
        return "Resolved"
    elif status in pending_statuses:
        return "Pending"
    else:
        return "In Progress"


def classify_age_duration(ticket_age):

    if pd.isna(ticket_age):
        return ""

    if ticket_age <= 2:
        return "0-2 days"

    elif ticket_age <= 5:
        return "3-5 days"

    elif ticket_age <= 10:
        return "6-10 days"

    elif ticket_age <= 20:
        return "11-20 days"

    elif ticket_age <= 30:
        return "21-30 days"

    elif ticket_age <= 60:
        return "1 to 2 months"

    else:
        return "> 2 months"


def fetch_jira_issues(jql: str, max_results: int = 5000):
    base_url = st.secrets["JIRA_BASE_URL"]
    email = st.secrets["JIRA_EMAIL"]
    api_token = st.secrets["JIRA_API_TOKEN"]

    url = f"{base_url}/rest/api/3/search/jql"

    fields = [
        "summary",
        "status",
        "priority",
        "assignee",
        "reporter",
        "created",
        "updated",
        "duedate",
        "resolution",
        "resolutiondate",
        "issuetype",
        "customfield_10002"
    ]

    all_issues = []
    next_page_token = None
    page_size = 100

    while len(all_issues) < max_results:
        payload = {
            "jql": jql,
            "maxResults": min(page_size, max_results - len(all_issues)),
            "fields": fields
        }

        if next_page_token:
            payload["nextPageToken"] = next_page_token

        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(email, api_token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )

        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        all_issues.extend(issues)

        next_page_token = data.get("nextPageToken")

        if not next_page_token or len(issues) == 0:
            break

    rows = []
    today = datetime.now(timezone.utc)

    for issue in all_issues:
        fields = issue.get("fields", {})

        status = fields.get("status", {}).get("name")
        created_raw = fields.get("created")
        updated_raw = fields.get("updated")

        created_dt = pd.to_datetime(created_raw, errors="coerce", utc=True)
        updated_dt = pd.to_datetime(updated_raw, errors="coerce", utc=True)

        ticket_age = (today - created_dt.to_pydatetime()).days if pd.notna(created_dt) else None

        organizations = fields.get("customfield_10002", [])
        if isinstance(organizations, list):
            org_names = ", ".join([org.get("name", "") for org in organizations])
        else:
            org_names = ""

        rows.append({
            "Issue Type": fields.get("issuetype", {}).get("name"),
            "Key": issue.get("key"),
            "Summary": fields.get("summary"),
            "Assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
            "Reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else "Unknown",
            "Priority": fields.get("priority", {}).get("name") if fields.get("priority") else "None",
            "Status": status,
            "Status Category": map_status_category(status),
            "Resolution": fields.get("resolution", {}).get("name") if fields.get("resolution") else "",
            "Resolved Date": fields.get("resolutiondate"),
            "Created": created_dt,
            "Updated": updated_dt,
            "Due date": fields.get("duedate"),
            "Organizations": org_names,
            "Year": created_dt.year if pd.notna(created_dt) else "",
            "Month": created_dt.strftime("%B") if pd.notna(created_dt) else "",
            "Ticket Age": ticket_age,
            "Ticket Age Duration": classify_age_duration(ticket_age),
            "Overdue": "More than 1 month" if ticket_age and ticket_age > 30 else "Less than 1 month"
        })

    return pd.DataFrame(rows)