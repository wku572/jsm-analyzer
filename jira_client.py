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


def _adf_to_text(node):
    if node is None:
        return ""

    if isinstance(node, str):
        return node

    if isinstance(node, list):
        return " ".join(_adf_to_text(item) for item in node)

    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return " ".join(_adf_to_text(child) for child in node.get("content", []))

    return ""


def _extract_internal_comment_text(fields_data):
    comments = fields_data.get("comment", {}).get("comments", [])

    # jsdPublic is this instance's internal/customer-visible flag (confirmed
    # live against the KSC project - there is no `visibility` object in use
    # here). A missing key is treated as unknown, not internal, rather than
    # silently including it - see the comment on fetch_jira_issues' `fields`
    # list for why the key can go missing if requested wrong.
    internal_comments = [c for c in comments if c.get("jsdPublic") is False]

    if not internal_comments:
        return ""

    return _adf_to_text(internal_comments[-1].get("body"))


def _extract_select_field_value(fields_data, field_id):
    field = fields_data.get(field_id)
    if isinstance(field, dict):
        return field.get("value")
    return None


# Jira's own field labels for these two custom fields are swapped relative to
# this app's "Impact Level" / "Urgency Level" vocabulary:
#   - Jira's "Urgency" field (customfield_10043) holds Critical/High/Medium/Low
#     values -> that's this app's IMPACT_LEVELS vocabulary.
#   - Jira's "Impact" field (customfield_10004) holds Extensive / Widespread,
#     Significant / Large, etc. -> that's this app's URGENCY_LEVELS vocabulary.
# Confirmed directly against real KSC tickets - do not "fix" this to look
# symmetric without re-checking, it's genuinely backwards in Jira's own setup.
JIRA_IMPACT_FIELD_ID = "customfield_10004"
JIRA_URGENCY_FIELD_ID = "customfield_10043"
JIRA_SEVERITY_FIELD_ID = "customfield_10049"


def _extract_escalation_level(fields_data):
    return _extract_select_field_value(fields_data, "customfield_11144")


def get_jira_secret(name):
    if name in st.secrets:
        return st.secrets[name]

    if "jira" in st.secrets:
        key = name.lower().replace("jira_", "")
        if key in st.secrets["jira"]:
            return st.secrets["jira"][key]

    return None


def update_issue_priority(
    issue_key: str,
    priority_name: str,
    jira_impact_value: str = None,
    jira_urgency_value: str = None,
    jira_severity_value: str = None,
):
    """Push Priority (native field) and, optionally, Jira's own Impact/Urgency/
    Severity select-list fields to a single Jira issue in one request.

    jira_impact_value/jira_urgency_value/jira_severity_value are Jira's field
    values directly (e.g. "Sev-1", not "SEV-1") - the caller is responsible
    for the impact/urgency swap and the severity format translation; this
    function does not re-map anything.
    """
    base_url = get_jira_secret("JIRA_BASE_URL")
    email = get_jira_secret("JIRA_EMAIL")
    api_token = get_jira_secret("JIRA_API_TOKEN")

    if not base_url or not email or not api_token:
        raise ValueError(
            "Missing Jira secrets. Please set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN."
        )

    base_url = base_url.rstrip("/")
    url = f"{base_url}/rest/api/3/issue/{issue_key}"

    fields = {"priority": {"name": priority_name}}
    if jira_impact_value is not None:
        fields[JIRA_IMPACT_FIELD_ID] = {"value": jira_impact_value}
    if jira_urgency_value is not None:
        fields[JIRA_URGENCY_FIELD_ID] = {"value": jira_urgency_value}
    if jira_severity_value is not None:
        fields[JIRA_SEVERITY_FIELD_ID] = {"value": jira_severity_value}

    response = requests.put(
        url,
        json={"fields": fields},
        auth=HTTPBasicAuth(email, api_token),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    )

    if response.status_code not in (200, 204):
        raise Exception(
            f"Jira priority update failed for {issue_key}. Status: {response.status_code}. Response: {response.text[:500]}"
        )


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
        "labels",
        "customfield_10002",
        "description",
        "comment",
        "customfield_11144",
        JIRA_IMPACT_FIELD_ID,
        JIRA_URGENCY_FIELD_ID,
        JIRA_SEVERITY_FIELD_ID
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
                f"Jira returned 0 issues. JQL: {jql}. Response: {str(data)[:2000]}"
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

        last_internal_comment = _extract_internal_comment_text(fields_data)

        rows.append({
            "Issue Type": fields_data.get("issuetype", {}).get("name"),
            "Key": issue.get("key"),
            "Summary": fields_data.get("summary"),
            "Assignee": fields_data.get("assignee", {}).get("displayName") if fields_data.get("assignee") else "Unassigned",
            "Reporter": fields_data.get("reporter", {}).get("displayName") if fields_data.get("reporter") else "Unknown",
            "Priority": fields_data.get("priority", {}).get("name") if fields_data.get("priority") else "None",
            "Status": status,
            "Status Category": map_status_category(status),
            "Labels": ", ".join(fields_data.get("labels", [])) if fields_data.get("labels") else "Unlabeled",
            "Resolution": fields_data.get("resolution", {}).get("name") if fields_data.get("resolution") else "",
            "Resolved Date": fields_data.get("resolutiondate"),
            "Created": created_dt,
            "Updated": updated_dt,
            "Due date": fields_data.get("duedate"),
            "Organizations": org_names,
            "Description": _adf_to_text(fields_data.get("description")),
            "Last Internal Comment": last_internal_comment,
            "Escalation Level": _extract_escalation_level(fields_data),
            "Jira Impact Field": _extract_select_field_value(fields_data, JIRA_IMPACT_FIELD_ID),
            "Jira Urgency Field": _extract_select_field_value(fields_data, JIRA_URGENCY_FIELD_ID),
            "Jira Severity Field": _extract_select_field_value(fields_data, JIRA_SEVERITY_FIELD_ID),
            "Year": created_dt.year if pd.notna(created_dt) else "",
            "Month": created_dt.strftime("%B") if pd.notna(created_dt) else "",
            "Ticket Age": ticket_age,
            "Ticket Age Duration": classify_age_duration(ticket_age),
            "Overdue": "More than 1 month" if ticket_age and ticket_age > 30 else "Less than 1 month"
        })

    return pd.DataFrame(rows)