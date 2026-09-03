import pandas as pd
import streamlit as st

from utils.ui import kpi_card
from utils.auth import is_support_admin
from utils.logger import write_audit_log
from utils.supabase_db import (
    save_incident_impact_assessment,
    load_incident_impact_assessments,
    update_incident_impact_assessment,
    delete_incident_impact_assessment,
    load_ga4_activity_records,
    calculate_ga4_weekday_baseline,
    calculate_ga4_rolling_mau_baseline
)
from jira_client import update_issue_priority


SEVERITY_STYLES = {
    "Low": "#16a34a",
    "Medium": "#f59e0b",
    "High": "#f97316",
    "Critical": "#dc2626",
}

SOURCE_OPTIONS = [
    "Bank confirmation",
    "Monitoring",
    "Log analysis",
    "Support estimate",
    "Product team",
    "Other",
]

WIZARD_STEPS = [
    "Select Ticket",
    "Review Baseline",
    "Enter Impact",
    "Save",
]

IMPACT_LEVELS = ["Critical", "High", "Medium", "Low"]

URGENCY_LEVELS = [
    "Extensive / Widespread",
    "Significant / Large",
    "Moderate / Limited",
    "Minor / Localized",
]

SEVERITY_BY_IMPACT = {
    "Critical": "SEV-0",
    "High": "SEV-1",
    "Medium": "SEV-2",
    "Low": "SEV-3",
}

PRIORITY_MATRIX = {
    "Low": {
        "Minor / Localized": "Lowest",
        "Moderate / Limited": "Low",
        "Significant / Large": "Medium",
        "Extensive / Widespread": "Medium",
    },
    "Medium": {
        "Minor / Localized": "Low",
        "Moderate / Limited": "Medium",
        "Significant / Large": "High",
        "Extensive / Widespread": "High",
    },
    "High": {
        "Minor / Localized": "Medium",
        "Moderate / Limited": "High",
        "Significant / Large": "Highest",
        "Extensive / Widespread": "Highest",
    },
    "Critical": {
        "Minor / Localized": "High",
        "Moderate / Limited": "Highest",
        "Significant / Large": "Highest",
        "Extensive / Widespread": "Highest",
    },
}


def _normalize_text(value, default=""):
    if pd.isna(value):
        return default
    text = str(value).strip()
    return text if text and text.lower() != "nan" else default


def _format_datetime(value):
    if value is None or pd.isna(value):
        return "N/A"

    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return "N/A"

    return ts.tz_convert("Africa/Addis_Ababa").strftime("%Y-%m-%d %H:%M:%S %Z")


def _severity_from_impact(impact_percentage):
    if impact_percentage < 5:
        return "Low"
    if impact_percentage < 15:
        return "Medium"
    if impact_percentage < 30:
        return "High"
    return "Critical"


def _compute_impact(expected_users, affected_users):
    if expected_users > 0 and affected_users >= 0:
        impact_percentage = round((affected_users / expected_users) * 100, 2)
        return impact_percentage, _severity_from_impact(impact_percentage)
    return None, "Not calculated"


def _compute_priority_severity(impact_level, urgency_level):
    priority = PRIORITY_MATRIX.get(impact_level, {}).get(urgency_level, "Medium")
    severity = SEVERITY_BY_IMPACT.get(impact_level, "SEV-2")
    return priority, severity


def _format_baseline_display(baseline_type):
    text = str(baseline_type or "").strip()
    if "Rolling 30-Day" in text:
        return "GA4 rolling 30-day baseline"
    if "Same-Weekday" in text:
        return "GA4 same-weekday baseline"
    return "Manual baseline"


def _baseline_mode_label(duration_type):
    if str(duration_type).strip() == "Multi-day":
        return "Multi-day incident"
    return "Single-day incident"


def _baseline_selection_explanation(duration_type):
    if str(duration_type).strip() == "Multi-day":
        return (
            "Multi-day incidents use a rolling 30-day activity baseline when GA4 history is available. "
            "If coverage is missing, the assessment remains in manual baseline mode."
        )

    return (
        "Single-day incidents use the previous same-weekday GA4 activity pattern when available. "
        "If coverage is missing, enter a manual expected customer baseline."
    )


def _confidence_from_record_count(record_count):
    try:
        count = int(record_count)
    except (TypeError, ValueError):
        count = 0

    if count >= 25:
        return "High"
    if count >= 15:
        return "Medium"
    if count >= 5:
        return "Low"
    if count > 0:
        return "Very Low"
    return "Not Available"


def _confidence_help_text(record_count):
    confidence = _confidence_from_record_count(record_count)
    if confidence == "High":
        return "Strong history available"
    if confidence == "Medium":
        return "Good history available"
    if confidence == "Low":
        return "Limited history available"
    if confidence == "Very Low":
        return "Very limited history available"
    return "No GA4 history available"


def _build_ga4_org_coverage(activity_df, organization):
    if activity_df is None or activity_df.empty:
        return {
            "available": False,
            "record_count": 0,
            "historical_days": 0,
            "first_date": None,
            "last_date": None,
            "records": None,
        }

    org_value = _normalize_text(organization).casefold()
    coverage_df = activity_df.copy()
    if "organization" not in coverage_df.columns:
        return {
            "available": False,
            "record_count": 0,
            "historical_days": 0,
            "first_date": None,
            "last_date": None,
            "records": None,
        }

    coverage_df["organization"] = coverage_df["organization"].fillna("").astype(str).str.strip()
    coverage_df = coverage_df[
        coverage_df["organization"].str.casefold() == org_value
    ]

    if coverage_df.empty:
        return {
            "available": False,
            "record_count": 0,
            "historical_days": 0,
            "first_date": None,
            "last_date": None,
            "records": None,
        }

    if "activity_date" in coverage_df.columns:
        coverage_df["activity_date"] = pd.to_datetime(coverage_df["activity_date"], errors="coerce")
        coverage_dates = coverage_df["activity_date"].dt.date.dropna()
    else:
        coverage_dates = pd.Series(dtype=object)

    unique_days = int(coverage_dates.nunique()) if not coverage_dates.empty else 0
    first_date = coverage_dates.min() if not coverage_dates.empty else None
    last_date = coverage_dates.max() if not coverage_dates.empty else None

    return {
        "available": True,
        "record_count": int(len(coverage_df)),
        "historical_days": unique_days,
        "first_date": first_date,
        "last_date": last_date,
        "records": coverage_df,
    }


def _build_summary(ticket_key, organization, affected_users, expected_users, impact_percentage, severity, baseline_display):
    return (
        f"Customer impact assessment for ticket {ticket_key} at {organization}. "
        f"An estimated {affected_users} users were affected out of {expected_users} expected active users, "
        f"resulting in a customer impact of {impact_percentage:.2f}%. "
        f"Suggested business impact: {severity}. "
        f"Baseline source: {baseline_display}."
    )


def _format_history_cell(value, column_name):
    if pd.isna(value):
        return ""

    if column_name == "created_at":
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return ""
        return ts.tz_convert("Africa/Addis_Ababa").strftime("%Y-%m-%d %H:%M:%S")

    if column_name == "impact_percentage":
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return str(value)

    return value


def _history_search_mask(df, search_text):
    if not search_text:
        return pd.Series([True] * len(df), index=df.index)

    search_text = search_text.lower().strip()
    searchable_columns = [
        "issue_key",
        "organization",
        "summary",
        "priority",
        "status",
        "labels",
        "assignee",
        "reporter",
        "affected_user_source",
        "suggested_severity",
        "created_by",
    ]

    mask = pd.Series([False] * len(df), index=df.index)

    for col in searchable_columns:
        if col in df.columns:
            mask = mask | df[col].fillna("").astype(str).str.lower().str.contains(search_text, na=False)

    return mask


def _history_label(row):
    created_at = row.get("created_at", "")
    if created_at:
        return (
            f"{row.get('issue_key', '')} | {row.get('organization', '')} | "
            f"{created_at}"
        )

    return f"{row.get('issue_key', '')} | {row.get('organization', '')}"


def _record_payload_from_inputs(
    issue_key,
    summary,
    organization,
    priority,
    status,
    labels,
    assignee,
    reporter,
    incident_start,
    incident_end,
    duration_hours,
    duration_type,
    expected_users,
    affected_users,
    impact_percentage,
    suggested_severity,
    affected_user_source,
    remarks,
    baseline_type,
    created_by,
    impact_level=None,
    urgency_level=None,
    computed_priority=None,
    computed_severity=None,
    jira_priority_pushed=False,
    jira_priority_pushed_at=None,
):
    return {
        "issue_key": issue_key,
        "summary": summary,
        "organization": organization,
        "priority": priority,
        "status": status,
        "labels": labels,
        "assignee": assignee,
        "reporter": reporter,
        "incident_start": incident_start.isoformat(),
        "incident_end": incident_end.isoformat(),
        "duration_hours": duration_hours,
        "duration_type": duration_type,
        "expected_users": int(expected_users),
        "affected_users": int(affected_users),
        "impact_percentage": impact_percentage,
        "suggested_severity": suggested_severity,
        "affected_user_source": affected_user_source,
        "remarks": remarks,
        "baseline_type": baseline_type,
        "created_by": created_by,
        "impact_level": impact_level,
        "urgency_level": urgency_level,
        "computed_priority": computed_priority,
        "computed_severity": computed_severity,
        "jira_priority_pushed": jira_priority_pushed,
        "jira_priority_pushed_at": jira_priority_pushed_at,
    }


def _parse_utc_timestamp(value):
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.Timestamp.now(tz="UTC")
    return ts


def _render_step_indicator(current_step):
    cols = st.columns(len(WIZARD_STEPS))

    for idx, label in enumerate(WIZARD_STEPS, start=1):
        if idx < current_step:
            bg, fg, border, marker = "#e8f7ef", "#166534", "#86efac", "✓"
        elif idx == current_step:
            bg, fg, border, marker = "#02404f", "#ffffff", "#02404f", str(idx)
        else:
            bg, fg, border, marker = "#f1f5f9", "#94a3b8", "#e2e8f0", str(idx)

        with cols[idx - 1]:
            st.markdown(
                f"""
                <div style="
                    border: 1px solid {border};
                    background: {bg};
                    color: {fg};
                    border-radius: 12px;
                    padding: 8px 6px;
                    text-align: center;
                    font-weight: 700;
                ">
                    <div style="font-size:14px;">{marker}</div>
                    <div style="margin-top:2px; font-size:11px;">{label}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.write("")


def _render_wizard_nav(show_back, next_label, step_key):
    nav_cols = st.columns([1, 1, 4])

    back_clicked = False
    with nav_cols[0]:
        if show_back:
            back_clicked = st.button("◀ Back", key=f"incident_wizard_back_{step_key}")

    with nav_cols[1]:
        next_clicked = st.button(next_label, type="primary", key=f"incident_wizard_next_{step_key}")

    return back_clicked, next_clicked


def _render_ticket_detail_table(
    issue_key, summary, organization, status, priority, labels, assignee, reporter,
    incident_start, resolved_value, duration_type, duration_hours
):
    detail_df = pd.DataFrame([{
        "Key": issue_key,
        "Summary": summary or "N/A",
        "Organization": organization,
        "Status": status,
        "Priority": priority,
        "Labels": labels,
        "Assignee": assignee,
        "Reporter": reporter,
        "Created": _format_datetime(incident_start),
        "Resolved Date": _format_datetime(resolved_value),
        "Duration Type": duration_type,
        "Duration Hours": f"{duration_hours:.2f}",
    }])

    st.dataframe(detail_df, width="stretch", hide_index=True)


def _render_step_select_ticket(ticket_df):
    st.markdown("### Step 1: Select Jira Ticket")

    ticket_search = st.text_input(
        "Search Jira tickets",
        placeholder="Search by ticket key, summary, organization, assignee, or reporter...",
        key="incident_ticket_search"
    )

    search_df = ticket_df
    if ticket_search.strip():
        ticket_mask = _history_search_mask(
            ticket_df.rename(columns={
                "Key": "issue_key",
                "Summary": "summary",
                "Organizations": "organization",
                "Priority": "priority",
                "Status": "status",
                "Labels": "labels",
                "Assignee": "assignee",
                "Reporter": "reporter",
            }),
            ticket_search
        )
        search_df = ticket_df[ticket_mask]

    if search_df.empty:
        st.info("No Jira tickets matched your search.")
        return

    search_df = search_df.reset_index(drop=True)

    ticket_options = [
        f"{row['Key']} - {str(row.get('Summary', '')).strip()[:90]}"
        if str(row.get("Summary", "")).strip()
        else row["Key"]
        for _, row in search_df.iterrows()
    ]

    selected_label = st.selectbox(
        "Select Jira ticket",
        ticket_options,
        key="incident_ticket_select"
    )

    selected_index = ticket_options.index(selected_label)
    ticket = search_df.iloc[selected_index]

    issue_key = _normalize_text(ticket.get("Key"))
    summary = _normalize_text(ticket.get("Summary"))
    organization = _normalize_text(ticket.get("Organizations"), "Unknown")
    status = _normalize_text(ticket.get("Status"), "Unknown")
    priority = _normalize_text(ticket.get("Priority"), "Unknown")

    st.caption(f"**{issue_key}** — {summary or 'No summary'}")
    st.caption(f"Organization: **{organization}** · Status: **{status}** · Priority: **{priority}**")

    if st.button("Next ▶", type="primary", key="incident_wizard_next_step1"):
        st.session_state["incident_selected_key"] = issue_key
        st.session_state["incident_wizard_step"] = 2
        st.rerun()


def _render_step_review_baseline(
    issue_key, summary, organization, status, priority, labels, assignee, reporter,
    incident_start, resolved_value, duration_type, duration_hours,
    ga4_baseline, ga4_activity_df, confidence_value,
    baseline_display, baseline_mode_label, baseline_explanation
):
    st.markdown("### Step 2: Review Baseline")

    if ga4_baseline is not None:
        banner_bg, banner_border, banner_text = "#e8f7ef", "#86efac", "#166534"
        banner_title = "GA4 baseline available"
        banner_subtitle = (
            f"{baseline_display} is ready for {organization}. "
            f"{ga4_baseline['lookback_used']} records were used to estimate {ga4_baseline['expected_users']:.2f} expected active users."
        )
        banner_records = str(int(ga4_baseline["lookback_used"]))
        banner_expected = f"{ga4_baseline['expected_users']:.2f}"
    else:
        banner_bg, banner_border, banner_text = "#fff7ed", "#fdba74", "#9a3412"
        banner_title = "GA4 baseline not available"
        banner_subtitle = (
            "No matching GA4 history was found for this organization yet. "
            "Use manual inputs or import GA4 activity records to enable a recommendation."
        )
        banner_records = "0"
        banner_expected = "N/A"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {banner_border};
            background: {banner_bg};
            color: {banner_text};
            border-radius: 16px;
            padding: 14px 16px;
            margin: 10px 0 6px 0;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        ">
            <div style="font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;">
                {banner_title}
            </div>
            <div style="margin-top: 4px; font-size: 14px; line-height: 1.5;">
                {banner_subtitle}
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top: 10px;">
                <span style="background: rgba(255,255,255,0.65); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;">Organization: {organization}</span>
                <span style="background: rgba(255,255,255,0.65); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;">Baseline type: {baseline_display}</span>
                <span style="background: rgba(255,255,255,0.65); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;">Historical records: {banner_records}</span>
                <span style="background: rgba(255,255,255,0.65); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;">Expected active users: {banner_expected}</span>
                <span style="background: rgba(255,255,255,0.65); padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700;">Confidence: {confidence_value}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.caption(f"{baseline_mode_label}: {baseline_explanation}")

    st.markdown("#### Ticket & Incident Details")
    _render_ticket_detail_table(
        issue_key, summary, organization, status, priority, labels, assignee, reporter,
        incident_start, resolved_value, duration_type, duration_hours
    )

    st.markdown("#### Baseline Recommendation")
    st.info(baseline_explanation)

    if ga4_baseline is None:
        st.warning(
            "No matching GA4 baseline was found for this incident. The assessment can continue using a manual baseline."
        )
    else:
        st.success(
            f"{baseline_display} found for {organization}. "
            f"{ga4_baseline['expected_users']:.2f} expected active users were estimated from {ga4_baseline['lookback_used']} records."
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Baseline Status", "Available")
        with c2:
            st.metric("Expected Active Users", f"{ga4_baseline['expected_users']:.2f}")
        with c3:
            st.metric("Records Used", int(ga4_baseline["lookback_used"]))
        with c4:
            st.metric("Confidence", confidence_value)

        baseline_records = ga4_baseline["records"].copy()
        preview_cols = [
            col for col in ["activity_date", "weekday", "hour", "active_users", "source", "excluded"]
            if col in baseline_records.columns
        ]
        st.dataframe(
            baseline_records[preview_cols],
            width="stretch",
            hide_index=True
        )

        if st.button(
            "Use GA4 Baseline",
            type="primary",
            key=f"incident_use_ga4_baseline_{issue_key}"
        ):
            st.session_state["incident_expected_users"] = int(round(ga4_baseline["expected_users"]))
            st.session_state["incident_baseline_source"] = ga4_baseline["baseline_type"]
            st.rerun()

    ga4_coverage = _build_ga4_org_coverage(ga4_activity_df, organization)
    st.markdown("#### GA4 Coverage Status")
    coverage_cols = st.columns(4)
    with coverage_cols[0]:
        st.metric("GA4 Activity", "Available" if ga4_coverage["available"] else "Missing")
    with coverage_cols[1]:
        st.metric("Historical Days", int(ga4_coverage["historical_days"]))
    with coverage_cols[2]:
        st.metric("Imported Rows", int(ga4_coverage["record_count"]))
    with coverage_cols[3]:
        st.metric("Coverage Ready", "Yes" if ga4_coverage["available"] else "No")

    if ga4_coverage["available"]:
        st.success(
            f"GA4 history exists for {organization} across {ga4_coverage['historical_days']} days "
            f"from {ga4_coverage['first_date']} to {ga4_coverage['last_date']}."
        )
    else:
        st.info(
            f"No GA4 activity coverage is currently available for {organization}. "
            "Import GA4 activity records to unlock the baseline recommendation."
        )


def _render_step_enter_impact(baseline_display):
    st.markdown("### Step 3: Enter Impact")

    input_cols = st.columns(2)

    with input_cols[0]:
        expected_users = st.number_input(
            "Expected Active Users",
            min_value=0,
            step=1,
            value=int(st.session_state.get("incident_expected_users", 0) or 0),
            key="incident_expected_users"
        )
        st.caption(
            "This field can be prefilled from GA4 when a matching baseline exists. You can still override it manually if needed."
        )
        if 0 < expected_users < 20:
            st.warning(
                "This is a very small baseline. It is allowed for testing, but it may produce unusually large impact percentages."
            )

        affected_users = st.number_input(
            "Estimated Affected Users",
            min_value=0,
            step=1,
            value=0,
            key="incident_affected_users"
        )

    with input_cols[1]:
        st.selectbox(
            "Affected User Source",
            SOURCE_OPTIONS,
            key="incident_source"
        )

        st.text_area(
            "Remarks",
            placeholder="Add any context about the incident impact assessment...",
            key="incident_remarks"
        )

    if expected_users == 0:
        st.warning("Expected Active Users must be greater than zero to calculate customer impact.")

    impact_percentage, suggested_severity = _compute_impact(expected_users, affected_users)

    st.markdown("#### Impact Preview")
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        kpi_card("Expected Active Users", expected_users, baseline_display, "👥")
    with k2:
        kpi_card("Estimated Affected Users", affected_users, "Manual estimate", "⚠️")
    with k3:
        impact_value = f"{impact_percentage:.2f}%" if impact_percentage is not None else "N/A"
        kpi_card("Customer Impact %", impact_value, "Affected / expected users", "📊")
    with k4:
        kpi_card("Suggested Business Impact", suggested_severity, "Impact-based recommendation", "🚦")

    st.markdown("#### JSM Triage Classification")
    triage_cols = st.columns(2)
    with triage_cols[0]:
        impact_level = st.selectbox(
            "Impact Level",
            IMPACT_LEVELS,
            key="incident_impact_level"
        )
    with triage_cols[1]:
        urgency_level = st.selectbox(
            "Urgency Level",
            URGENCY_LEVELS,
            key="incident_urgency_level"
        )

    computed_priority, computed_severity = _compute_priority_severity(impact_level, urgency_level)

    p1, p2 = st.columns(2)
    with p1:
        kpi_card("Computed Priority", computed_priority, "Impact × Urgency matrix", "\U0001F6a9")
    with p2:
        kpi_card("Computed Severity", computed_severity, f"{impact_level} impact", "\U0001F6a8")


def _render_step_save(issue_key, organization, baseline_display, current_priority):
    st.markdown("### Step 4: Save Assessment")

    expected_users = int(st.session_state.get("incident_expected_users", 0) or 0)
    affected_users = int(st.session_state.get("incident_affected_users", 0) or 0)
    impact_percentage, suggested_severity = _compute_impact(expected_users, affected_users)

    impact_level = st.session_state.get("incident_impact_level", IMPACT_LEVELS[0])
    urgency_level = st.session_state.get("incident_urgency_level", URGENCY_LEVELS[0])
    computed_priority, computed_severity = _compute_priority_severity(impact_level, urgency_level)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Expected Active Users", expected_users, baseline_display, "👥")
    with k2:
        kpi_card("Estimated Affected Users", affected_users, "Manual estimate", "⚠️")
    with k3:
        impact_value = f"{impact_percentage:.2f}%" if impact_percentage is not None else "N/A"
        kpi_card("Customer Impact %", impact_value, "Affected / expected users", "📊")
    with k4:
        kpi_card("Suggested Business Impact", suggested_severity, "Impact-based recommendation", "🚦")

    p1, p2 = st.columns(2)
    with p1:
        kpi_card("Computed Priority", computed_priority, f"{impact_level} × {urgency_level}", "\U0001F6a9")
    with p2:
        kpi_card("Computed Severity", computed_severity, f"{impact_level} impact", "\U0001F6a8")

    if is_support_admin():
        if computed_priority == current_priority:
            st.caption(f"Jira ticket priority already matches: **{current_priority}**.")
        else:
            st.checkbox(
                f"Also update this ticket's Priority in Jira from **{current_priority}** to **{computed_priority}**",
                key="incident_push_priority_to_jira"
            )

    st.markdown("#### Executive Summary")
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:6px 12px;
            border-radius:999px;
            background:#eef6fb;
            color:#0b4f63;
            font-weight:700;
            font-size:12px;
            margin-bottom:10px;
        ">
            Baseline Source: {baseline_display}
        </div>
        """,
        unsafe_allow_html=True
    )

    if impact_percentage is not None:
        summary_text = _build_summary(
            issue_key,
            organization,
            int(affected_users),
            int(expected_users),
            impact_percentage,
            suggested_severity,
            baseline_display
        )
    else:
        summary_text = (
            f"Ticket {issue_key} for {organization} is ready for customer impact assessment. "
            "Enter a valid Expected Active Users value to calculate impact. "
            f"Baseline source: {baseline_display}."
        )

    st.info(summary_text)


def _handle_save_assessment(
    issue_key, summary, organization, priority, status, labels, assignee, reporter,
    incident_start, incident_end, duration_hours, duration_type
):
    expected_users = int(st.session_state.get("incident_expected_users", 0) or 0)
    affected_users = int(st.session_state.get("incident_affected_users", 0) or 0)
    affected_user_source = st.session_state.get("incident_source", SOURCE_OPTIONS[0])
    remarks = st.session_state.get("incident_remarks", "")
    baseline_label = st.session_state.get("incident_baseline_source", "Manual baseline")

    impact_level = st.session_state.get("incident_impact_level", IMPACT_LEVELS[0])
    urgency_level = st.session_state.get("incident_urgency_level", URGENCY_LEVELS[0])
    computed_priority, computed_severity = _compute_priority_severity(impact_level, urgency_level)

    if expected_users <= 0:
        st.warning("Expected Active Users must be greater than zero before saving.")
        return

    if affected_users < 0:
        st.warning("Estimated Affected Users must be zero or greater before saving.")
        return

    impact_to_save, severity_to_save = _compute_impact(expected_users, affected_users)
    current_user = st.session_state.get("user_email", "")
    current_role = st.session_state.get("user_role", "")

    push_requested = (
        is_support_admin()
        and st.session_state.get("incident_push_priority_to_jira", False)
        and computed_priority != priority
    )

    payload = _record_payload_from_inputs(
        issue_key,
        summary,
        organization,
        priority,
        status,
        labels,
        assignee,
        reporter,
        incident_start,
        incident_end,
        duration_hours,
        duration_type,
        expected_users,
        affected_users,
        impact_to_save,
        severity_to_save,
        affected_user_source,
        remarks,
        baseline_label,
        current_user,
        impact_level=impact_level,
        urgency_level=urgency_level,
        computed_priority=computed_priority,
        computed_severity=computed_severity,
    )

    try:
        record_id = save_incident_impact_assessment(payload)
        st.success("Assessment saved successfully.")
    except Exception as exc:
        st.error("Failed to save incident impact assessment.")
        st.exception(exc)
        return

    if push_requested:
        try:
            update_issue_priority(issue_key, computed_priority)
            pushed_at = pd.Timestamp.now(tz="UTC").isoformat()

            if record_id is not None:
                update_incident_impact_assessment(record_id, {
                    "jira_priority_pushed": True,
                    "jira_priority_pushed_at": pushed_at,
                })

            write_audit_log(
                current_user,
                current_role,
                "JIRA_PRIORITY_UPDATE",
                f"{issue_key}: {priority} -> {computed_priority}"
            )
            st.success(f"Jira ticket {issue_key} priority updated to {computed_priority}.")
        except Exception as exc:
            st.error("The assessment was saved, but updating the Jira ticket's priority failed.")
            st.exception(exc)

    st.session_state["incident_wizard_step"] = 1
    st.rerun()


def _render_assessment_wizard(ticket_df):
    current_step = st.session_state.get("incident_wizard_step", 1)

    _render_step_indicator(current_step)

    if current_step == 1:
        _render_step_select_ticket(ticket_df)
        return

    selected_key = st.session_state.get("incident_selected_key")
    matches = ticket_df[ticket_df["Key"] == selected_key]

    if matches.empty:
        st.warning("The previously selected ticket is no longer available. Returning to ticket selection.")
        st.session_state["incident_wizard_step"] = 1
        st.rerun()
        return

    ticket = matches.iloc[0]

    issue_key = _normalize_text(ticket.get("Key"))
    summary = _normalize_text(ticket.get("Summary"))
    organization = _normalize_text(ticket.get("Organizations"), "Unknown")
    priority = _normalize_text(ticket.get("Priority"), "Unknown")
    status = _normalize_text(ticket.get("Status"), "Unknown")
    labels = _normalize_text(ticket.get("Labels"), "Unlabeled")
    assignee = _normalize_text(ticket.get("Assignee"), "Unassigned")
    reporter = _normalize_text(ticket.get("Reporter"), "Unknown")
    created_value = ticket.get("Created")
    resolved_value = ticket.get("Resolved Date")
    local_timezone = "Africa/Addis_Ababa"

    incident_start = pd.to_datetime(created_value, errors="coerce", utc=True)
    if pd.isna(incident_start):
        incident_start = pd.Timestamp.now(tz="UTC")

    incident_end = pd.to_datetime(resolved_value, errors="coerce", utc=True)
    if pd.isna(incident_end):
        incident_end = pd.Timestamp.now(tz="UTC")

    duration_hours = round(
        (incident_end - incident_start).total_seconds() / 3600,
        2
    )
    duration_type = (
        "Single-day"
        if incident_start.date() == incident_end.date()
        else "Multi-day"
    )

    incident_local = incident_start.tz_convert(local_timezone)
    incident_weekday = incident_local.strftime("%A")

    try:
        ga4_activity_df = load_ga4_activity_records()
    except Exception:
        ga4_activity_df = None

    if duration_type == "Single-day":
        ga4_baseline = calculate_ga4_weekday_baseline(
            organization,
            incident_weekday,
            incident_date=incident_start
        )
    else:
        ga4_baseline = calculate_ga4_rolling_mau_baseline(
            organization,
            incident_date=incident_start
        )

    ticket_changed = st.session_state.get("incident_last_ticket") != issue_key
    if ticket_changed:
        st.session_state["incident_last_ticket"] = issue_key
        st.session_state["incident_affected_users"] = 0
        st.session_state["incident_remarks"] = ""
        st.session_state["incident_source"] = SOURCE_OPTIONS[0]
        st.session_state["incident_impact_level"] = "Medium"
        st.session_state["incident_urgency_level"] = "Moderate / Limited"
        st.session_state["incident_push_priority_to_jira"] = False

        if ga4_baseline is not None:
            st.session_state["incident_expected_users"] = int(round(ga4_baseline["expected_users"]))
            st.session_state["incident_baseline_source"] = ga4_baseline["baseline_type"]
        else:
            st.session_state["incident_expected_users"] = 0
            st.session_state["incident_baseline_source"] = "Manual baseline"

    elif ga4_baseline is not None and st.session_state.get("incident_baseline_source") != ga4_baseline["baseline_type"]:
        st.session_state["incident_expected_users"] = int(round(ga4_baseline["expected_users"]))
        st.session_state["incident_baseline_source"] = ga4_baseline["baseline_type"]

    confidence_value = _confidence_from_record_count(
        ga4_baseline["lookback_used"] if ga4_baseline is not None else 0
    )
    baseline_label = st.session_state.get("incident_baseline_source", "Manual baseline")
    baseline_display = _format_baseline_display(baseline_label)
    baseline_mode_label = _baseline_mode_label(duration_type)
    baseline_explanation = _baseline_selection_explanation(duration_type)

    if current_step == 2:
        _render_step_review_baseline(
            issue_key, summary, organization, status, priority, labels, assignee, reporter,
            incident_start, resolved_value, duration_type, duration_hours,
            ga4_baseline, ga4_activity_df, confidence_value,
            baseline_display, baseline_mode_label, baseline_explanation
        )

        back_clicked, next_clicked = _render_wizard_nav(True, "Next ▶", "step2")
        if back_clicked:
            st.session_state["incident_wizard_step"] = 1
            st.rerun()
        if next_clicked:
            st.session_state["incident_wizard_step"] = 3
            st.rerun()

    elif current_step == 3:
        _render_step_enter_impact(baseline_display)

        back_clicked, next_clicked = _render_wizard_nav(True, "Next ▶", "step3")
        if back_clicked:
            st.session_state["incident_wizard_step"] = 2
            st.rerun()
        if next_clicked:
            expected_users = int(st.session_state.get("incident_expected_users", 0) or 0)
            if expected_users <= 0:
                st.warning("Expected Active Users must be greater than zero to continue.")
            else:
                st.session_state["incident_wizard_step"] = 4
                st.rerun()

    elif current_step == 4:
        _render_step_save(issue_key, organization, baseline_display, priority)

        back_clicked, save_clicked = _render_wizard_nav(True, "Save Assessment", "step4")
        if back_clicked:
            st.session_state["incident_wizard_step"] = 3
            st.rerun()
        if save_clicked:
            _handle_save_assessment(
                issue_key, summary, organization, priority, status, labels, assignee, reporter,
                incident_start, incident_end, duration_hours, duration_type
            )


def _render_history_tab():
    history_df = load_incident_impact_assessments()

    if history_df is None or history_df.empty:
        st.info("No saved incident impact assessments yet.")
        return

    display_rows = []
    for _, row in history_df.iterrows():
        display_rows.append({
            "Ticket": _normalize_text(row.get("issue_key")),
            "Organization": _normalize_text(row.get("organization")),
            "Baseline Source": _format_baseline_display(row.get("baseline_type")),
            "Expected Users": _normalize_text(row.get("expected_users")),
            "Affected Users": _normalize_text(row.get("affected_users")),
            "Impact %": _format_history_cell(row.get("impact_percentage"), "impact_percentage"),
            "Business Impact": _normalize_text(row.get("suggested_severity")),
            "Impact Level": _normalize_text(row.get("impact_level")),
            "Urgency Level": _normalize_text(row.get("urgency_level")),
            "Priority": _normalize_text(row.get("computed_priority")),
            "Severity": _normalize_text(row.get("computed_severity")),
            "Jira Synced": "Yes" if row.get("jira_priority_pushed") else "No",
            "Created By": _normalize_text(row.get("created_by")),
            "Assessment Date": _format_history_cell(row.get("created_at"), "created_at"),
        })

    history_view = pd.DataFrame(display_rows)

    if history_view.empty:
        st.info("No saved incident impact assessments yet.")
    else:
        st.dataframe(
            history_view,
            width="stretch",
            hide_index=True
        )

    st.markdown("### Manage Saved Assessments")

    management_search = st.text_input(
        "Search saved assessments",
        placeholder="Search by ticket key, organization, assignee, reporter, or source...",
        key="incident_history_search"
    )

    management_df = history_df.copy()
    if management_search.strip():
        management_df = management_df[_history_search_mask(management_df, management_search)]

    if management_df.empty:
        st.info("No saved assessments matched your search.")
        return

    if "created_at" in management_df.columns:
        management_df["created_at"] = pd.to_datetime(
            management_df["created_at"],
            errors="coerce",
            utc=True
        )
        management_df = management_df.sort_values("created_at", ascending=False)

    management_df = management_df.reset_index(drop=True)
    management_options = management_df.apply(_history_label, axis=1).tolist()

    selected_management_label = st.selectbox(
        "Select assessment to edit or delete",
        management_options,
        key="incident_history_select"
    )

    selected_management_index = management_options.index(selected_management_label)
    selected_record = management_df.iloc[selected_management_index]
    record_id = selected_record.get("id")

    same_ticket_count = 0
    if "issue_key" in management_df.columns:
        same_ticket_count = int(
            management_df["issue_key"].fillna("").astype(str).eq(
                _normalize_text(selected_record.get("issue_key"))
            ).sum()
        )
    if same_ticket_count > 1:
        st.warning(
            f"There are {same_ticket_count} assessments for ticket {selected_record.get('issue_key')}. "
            "Use edit or delete to keep the record set clean."
        )

    edit_cols = st.columns(2)

    with edit_cols[0]:
        edit_issue_key = st.text_input(
            "Issue Key",
            value=_normalize_text(selected_record.get("issue_key")),
            key=f"incident_edit_issue_key_{record_id}"
        )
        edit_organization = st.text_input(
            "Organization",
            value=_normalize_text(selected_record.get("organization")),
            key=f"incident_edit_organization_{record_id}"
        )
        edit_priority = st.text_input(
            "Priority",
            value=_normalize_text(selected_record.get("priority")),
            key=f"incident_edit_priority_{record_id}"
        )
        edit_status = st.text_input(
            "Status",
            value=_normalize_text(selected_record.get("status")),
            key=f"incident_edit_status_{record_id}"
        )
        edit_labels = st.text_input(
            "Labels",
            value=_normalize_text(selected_record.get("labels")),
            key=f"incident_edit_labels_{record_id}"
        )

    with edit_cols[1]:
        edit_assignee = st.text_input(
            "Assignee",
            value=_normalize_text(selected_record.get("assignee")),
            key=f"incident_edit_assignee_{record_id}"
        )
        edit_reporter = st.text_input(
            "Reporter",
            value=_normalize_text(selected_record.get("reporter")),
            key=f"incident_edit_reporter_{record_id}"
        )
        edit_source = st.selectbox(
            "Affected User Source",
            SOURCE_OPTIONS,
            key=f"incident_edit_source_{record_id}",
            index=SOURCE_OPTIONS.index(_normalize_text(selected_record.get("affected_user_source"), SOURCE_OPTIONS[0]))
            if _normalize_text(selected_record.get("affected_user_source"), SOURCE_OPTIONS[0]) in SOURCE_OPTIONS
            else 0
        )
        edit_baseline_type = st.text_input(
            "Baseline Source",
            value=_normalize_text(selected_record.get("baseline_type"), "Manual baseline"),
            key=f"incident_edit_baseline_type_{record_id}"
        )
        edit_remarks = st.text_area(
            "Remarks",
            value=_normalize_text(selected_record.get("remarks")),
            key=f"incident_edit_remarks_{record_id}"
        )

    edit_num_cols = st.columns(3)
    with edit_num_cols[0]:
        edit_expected_users = st.number_input(
            "Expected Active Users",
            min_value=0,
            step=1,
            value=int(selected_record.get("expected_users", 0) or 0),
            key=f"incident_edit_expected_users_{record_id}"
        )
    with edit_num_cols[1]:
        edit_affected_users = st.number_input(
            "Estimated Affected Users",
            min_value=0,
            step=1,
            value=int(selected_record.get("affected_users", 0) or 0),
            key=f"incident_edit_affected_users_{record_id}"
        )
    with edit_num_cols[2]:
        st.text_input(
            "Impact % (auto-calculated)",
            value=str(selected_record.get("impact_percentage", "")),
            disabled=True,
            key=f"incident_edit_impact_{record_id}"
        )

    st.markdown("#### JSM Triage Classification")
    triage_edit_cols = st.columns(2)

    stored_impact_level = _normalize_text(selected_record.get("impact_level"), IMPACT_LEVELS[2])
    stored_urgency_level = _normalize_text(selected_record.get("urgency_level"), URGENCY_LEVELS[2])

    with triage_edit_cols[0]:
        edit_impact_level = st.selectbox(
            "Impact Level",
            IMPACT_LEVELS,
            index=IMPACT_LEVELS.index(stored_impact_level) if stored_impact_level in IMPACT_LEVELS else 2,
            key=f"incident_edit_impact_level_{record_id}"
        )
    with triage_edit_cols[1]:
        edit_urgency_level = st.selectbox(
            "Urgency Level",
            URGENCY_LEVELS,
            index=URGENCY_LEVELS.index(stored_urgency_level) if stored_urgency_level in URGENCY_LEVELS else 2,
            key=f"incident_edit_urgency_level_{record_id}"
        )

    edit_computed_priority, edit_computed_severity = _compute_priority_severity(edit_impact_level, edit_urgency_level)
    st.caption(f"Computed Priority: **{edit_computed_priority}** · Computed Severity: **{edit_computed_severity}**")

    edit_actions = st.columns(2)
    with edit_actions[0]:
        if st.button("Update Assessment", type="primary", key=f"incident_update_{record_id}"):
            if edit_expected_users <= 0:
                st.warning("Expected Active Users must be greater than zero before updating.")
            else:
                try:
                    new_impact, new_severity = _compute_impact(edit_expected_users, edit_affected_users)

                    update_payload = _record_payload_from_inputs(
                        edit_issue_key,
                        selected_record.get("summary", ""),
                        edit_organization,
                        edit_priority,
                        edit_status,
                        edit_labels,
                        edit_assignee,
                        edit_reporter,
                        _parse_utc_timestamp(selected_record.get("incident_start")),
                        _parse_utc_timestamp(selected_record.get("incident_end")),
                        float(selected_record.get("duration_hours", 0) or 0),
                        _normalize_text(selected_record.get("duration_type")),
                        edit_expected_users,
                        edit_affected_users,
                        new_impact,
                        new_severity,
                        edit_source,
                        edit_remarks,
                        edit_baseline_type,
                        selected_record.get("created_by", ""),
                        impact_level=edit_impact_level,
                        urgency_level=edit_urgency_level,
                        computed_priority=edit_computed_priority,
                        computed_severity=edit_computed_severity,
                        jira_priority_pushed=bool(selected_record.get("jira_priority_pushed", False)),
                        jira_priority_pushed_at=selected_record.get("jira_priority_pushed_at"),
                    )
                    update_incident_impact_assessment(record_id, update_payload)
                    st.success("Assessment updated successfully.")
                    st.rerun()
                except Exception as exc:
                    st.error("Failed to update the assessment.")
                    st.exception(exc)

    with edit_actions[1]:
        confirm_delete = st.checkbox(
            "Confirm delete of selected assessment",
            key=f"confirm_delete_{record_id}"
        )
        if st.button("Delete Assessment", key=f"incident_delete_{record_id}") and confirm_delete:
            try:
                delete_incident_impact_assessment(record_id)
                st.success("Assessment deleted successfully.")
                st.rerun()
            except Exception as exc:
                st.error("Failed to delete the assessment.")
                st.exception(exc)


def render(filtered_df):
    st.title("Incident Impact Assessment")

    if filtered_df is None or filtered_df.empty:
        st.info("No ticket data is available for incident impact assessment.")
        return

    ticket_df = filtered_df.copy()

    if "Key" not in ticket_df.columns:
        st.info("The current dataset does not contain Jira ticket keys.")
        return

    ticket_df["Key"] = ticket_df["Key"].fillna("").astype(str)
    ticket_df = ticket_df[ticket_df["Key"].str.strip() != ""]

    if ticket_df.empty:
        st.info("No selectable Jira tickets are available.")
        return

    ticket_df = ticket_df.reset_index(drop=True)

    assess_tab, history_tab = st.tabs(["New Assessment", "Assessment History"])

    with assess_tab:
        _render_assessment_wizard(ticket_df)

    with history_tab:
        _render_history_tab()
