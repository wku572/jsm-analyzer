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


def get_jira_secret(name):
    if name in st.secrets:
        return st.secrets[name]

    if "jira" in st.secrets:
        key = name.lower().replace("jira_", "")
        if key in st.secrets["jira"]:
            return st.secrets["jira"][key]

    return None


def fetch_jira_issues(jql: str, max_results: int = 5000):
    base_url = get_jira_secret("JIRA_BASE_URL")
    email = get_jira_secret("JIRA_EMAIL")
    api_token = get_jira_secret("JIRA_API_TOKEN")

    if not base_url or not email or not api_token:
        raise ValueError(
            "Missing Jira secrets. Please set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
        )

    base_url = base_url.rstrip("/")
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
       

        if response.status_code != 200:
            raise Exception(
                f"Jira API failed. Status: {response.status_code}. Response: {response.text[:500]}"
            )

        data = response.json()

        issues = data.get("issues", [])

        if not issues:
            raise Exception(
                f"Jira returned 0 issues. JQL: {jql}. Response: {str(data)[:1000]}"
            )
        # if not issues:
        #     break

        all_issues.extend(issues)

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

    rows = []
    today = datetime.now(timezone.utc)

    for issue in all_issues:
        fields_data = issue.get("fields", {})

        status = fields_data.get("status", {}).get("name")
        created_raw = fields_data.get("created")
        updated_raw = fields_data.get("updated")

        created_dt = pd.to_datetime(created_raw, errors="coerce", utc=True)
        updated_dt = pd.to_datetime(updated_raw, errors="coerce", utc=True)

        ticket_age = (
            (today - created_dt.to_pydatetime()).days
            if pd.notna(created_dt)
            else None
        )

        organizations = fields_data.get("customfield_10002", [])

        if isinstance(organizations, list):
            org_names = ", ".join(
                [
                    org.get("name", "")
                    for org in organizations
                    if isinstance(org, dict)
                ]
            )
        else:
            org_names = ""

        rows.append({
            "Issue Type": fields_data.get("issuetype", {}).get("name"),
            "Key": issue.get("key"),
            "Summary": fields_data.get("summary"),
            "Assignee": fields_data.get("assignee", {}).get("displayName") if fields_data.get("assignee") else "Unassigned",
            "Reporter": fields_data.get("reporter", {}).get("displayName") if fields_data.get("reporter") else "Unknown",
            "Priority": fields_data.get("priority", {}).get("name") if fields_data.get("priority") else "None",
            "Status": status,
            "Status Category": map_status_category(status),
            "Resolution": fields_data.get("resolution", {}).get("name") if fields_data.get("resolution") else "",
            "Resolved Date": fields_data.get("resolutiondate"),
            "Created": created_dt,
            "Updated": updated_dt,
            "Due date": fields_data.get("duedate"),
            "Organizations": org_names,
            "Year": created_dt.year if pd.notna(created_dt) else "",
            "Month": created_dt.strftime("%B") if pd.notna(created_dt) else "",
            "Ticket Age": ticket_age,
            "Ticket Age Duration": classify_age_duration(ticket_age),
            "Overdue": "More than 1 month" if ticket_age and ticket_age > 30 else "Less than 1 month"
        })

    return pd.DataFrame(rows)