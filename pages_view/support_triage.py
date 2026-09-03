import pandas as pd
import streamlit as st

from jira_client import fetch_jira_issues
from utils.ticket_index import (
    tickets_from_dataframe,
    build_ticket_index,
    retrieve_similar_tickets,
    get_index_stats,
)
from utils.claude_triage import triage_ticket, parse_triage_response, describe_error
from utils.feedback_log import log_feedback


DEFAULT_JQL = "project = KSC ORDER BY created DESC"
MAX_INDEX_TICKETS = 2000


def _render_decision_banner(is_l1):
    if is_l1:
        bg, border, text_color, title = "#e8f7ef", "#86efac", "#166534", "L1 Resolvable"
    else:
        bg, border, text_color, title = "#fff7ed", "#fdba74", "#9a3412", "Escalate to L2+"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            background: {bg};
            color: {text_color};
            border-radius: 16px;
            padding: 14px 16px;
            margin: 10px 0;
        ">
            <div style="font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;">
                {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _log_current_feedback(parsed, thumbs):
    ticket_text = st.session_state.get("support_triage_last_ticket_text", "")
    response_text = parsed.get("draft_response") or parsed.get("escalation_summary") or ""

    log_feedback(
        ticket_text=ticket_text,
        decision=parsed.get("decision", ""),
        confidence=parsed.get("confidence", ""),
        response_text=response_text,
        thumbs=thumbs,
        user_email=st.session_state.get("user_email", ""),
    )
    st.toast("Feedback logged.")


def _render_result(parsed, similar):
    is_l1 = "L1" in parsed.get("decision", "").upper()

    _render_decision_banner(is_l1)
    st.metric("Confidence", parsed.get("confidence") or "N/A")

    if is_l1:
        st.markdown("#### Draft Response")
        st.text_area(
            "Suggested reply to the customer/reporter",
            value=parsed.get("draft_response", ""),
            height=150,
            disabled=True,
            key="support_triage_draft_response_display"
        )
    else:
        st.markdown("#### Escalation Summary")
        st.text_area(
            "Summary for L2+",
            value=parsed.get("escalation_summary", ""),
            height=150,
            disabled=True,
            key="support_triage_escalation_summary_display"
        )

    if similar:
        st.markdown("#### Similar Past Tickets Used")
        similar_df = pd.DataFrame(similar).rename(columns={
            "ticket_id": "Ticket",
            "escalation_level": "Escalation Level",
            "text": "Summary + Resolution",
        })
        st.dataframe(similar_df, width="stretch", hide_index=True)
    else:
        st.info("No similar past tickets were found in the index for this ticket.")

    st.markdown("#### Was this helpful?")
    feedback_cols = st.columns([1, 1, 4])
    with feedback_cols[0]:
        if st.button("👍 Helpful", key="support_triage_thumbs_up"):
            _log_current_feedback(parsed, "up")
    with feedback_cols[1]:
        if st.button("👎 Not quite right", key="support_triage_thumbs_down"):
            _log_current_feedback(parsed, "down")


def render(filtered_df):
    st.title("Support Triage Agent")
    st.caption(
        "Paste a new ticket to get an L1/escalation recommendation, based on similar resolved KSC tickets."
    )

    stats = get_index_stats()
    index_count = stats["count"]

    status_cols = st.columns([3, 1])
    with status_cols[0]:
        if index_count > 0:
            st.success(f"Ticket index ready: {index_count} resolved tickets indexed.")
        else:
            st.warning("Ticket index is empty. Click \"Refresh ticket index\" before triaging.")
    with status_cols[1]:
        refresh_clicked = st.button(
            "🔄 Refresh ticket index",
            type="primary",
            width="stretch"
        )

    if refresh_clicked:
        with st.spinner("Pulling resolved KSC tickets from Jira and rebuilding the index..."):
            try:
                jira_df = fetch_jira_issues(DEFAULT_JQL, max_results=MAX_INDEX_TICKETS)
                tickets = tickets_from_dataframe(jira_df)
                indexed_count = build_ticket_index(tickets)

                if indexed_count == 0:
                    st.warning("No resolved tickets were found to index.")
                else:
                    st.success(f"Indexed {indexed_count} resolved tickets.")
                    st.rerun()
            except Exception as exc:
                st.error("Couldn't refresh the ticket index. Check the Jira connection and try again.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    st.divider()

    ticket_text = st.text_area(
        "New ticket description",
        height=150,
        placeholder="e.g. User reports login fails after password reset...",
        key="support_triage_ticket_text"
    )

    if st.button("Triage Ticket", type="primary"):
        if not ticket_text.strip():
            st.warning("Enter a ticket description before triaging.")
        elif index_count == 0:
            st.warning("The ticket index is empty. Refresh the index before triaging.")
        else:
            with st.spinner("Analyzing against ticket history..."):
                try:
                    similar = retrieve_similar_tickets(ticket_text)
                    raw_response = triage_ticket(ticket_text, similar)
                    parsed = parse_triage_response(raw_response)

                    st.session_state["support_triage_last_ticket_text"] = ticket_text
                    st.session_state["support_triage_last_result"] = parsed
                    st.session_state["support_triage_last_similar"] = similar
                except RuntimeError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Couldn't triage this ticket. {describe_error(exc)}")
                    with st.expander("Technical details"):
                        st.code(str(exc))

    result = st.session_state.get("support_triage_last_result")
    if result:
        _render_result(result, st.session_state.get("support_triage_last_similar", []))
