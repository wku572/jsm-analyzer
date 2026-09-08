import pandas as pd
import streamlit as st

from jira_client import fetch_jira_issues
from utils.ui import kpi_card
from utils.ticket_index import (
    tickets_from_dataframe,
    build_ticket_index,
    retrieve_similar_tickets,
    get_index_stats,
)
from utils.gemini_triage import triage_ticket, parse_triage_response, describe_error
from utils.feedback_log import log_feedback


DEFAULT_JQL = "project = KSC ORDER BY created DESC"
MAX_INDEX_TICKETS = 2000


def _render_banner(title, subtitle, tone):
    bg, border, text_color = {
        "success": ("#e8f7ef", "#86efac", "#166534"),
        "warning": ("#fff7ed", "#fdba74", "#9a3412"),
    }[tone]

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            background: {bg};
            color: {text_color};
            border-radius: 16px;
            padding: 14px 16px;
            margin: 10px 0 16px 0;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        ">
            <div style="font-weight: 800; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em;">
                {title}
            </div>
            <div style="margin-top: 4px; font-size: 14px; line-height: 1.5;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_decision_banner(is_l1):
    if is_l1:
        bg, border, text_color, title = "#e8f7ef", "#86efac", "#166534", "✅ L1 Resolvable"
    else:
        bg, border, text_color, title = "#fff7ed", "#fdba74", "#9a3412", "🚨 Escalate to L2+"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            background: {bg};
            color: {text_color};
            border-radius: 16px;
            padding: 16px 18px;
            margin: 6px 0 16px 0;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        ">
            <div style="font-weight: 800; font-size: 16px; letter-spacing: 0.02em;">
                {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_investigation_source_input(label, key_prefix):
    st.markdown(f"**{label}**")

    text = st.text_area(
        f"{label} findings",
        key=f"{key_prefix}_text",
        label_visibility="collapsed",
        placeholder="Paste findings or JSON here...",
        height=100,
    )

    uploaded_files = st.file_uploader(
        f"{label} files",
        type=["png", "jpg", "jpeg", "json", "txt"],
        key=f"{key_prefix}_file",
        label_visibility="collapsed",
        accept_multiple_files=True,
    )

    files = [
        {"bytes": f.getvalue(), "mime": f.type or "application/octet-stream"}
        for f in (uploaded_files or [])
    ]

    return {"label": label, "text": text, "files": files}


def _combine_feedback_text(parsed):
    sections = []
    if parsed.get("investigation_summary"):
        sections.append(f"Investigation Summary:\n{parsed['investigation_summary']}")
    if parsed.get("assignee_comment"):
        sections.append(f"Assignee Comment:\n{parsed['assignee_comment']}")
    if parsed.get("reporter_comment"):
        sections.append(f"Reporter Comment:\n{parsed['reporter_comment']}")

    if sections:
        return "\n\n".join(sections)

    return parsed.get("draft_response") or parsed.get("escalation_summary") or ""


def _log_current_feedback(parsed, thumbs):
    ticket_text = st.session_state.get("support_triage_last_ticket_text", "")

    log_feedback(
        ticket_text=ticket_text,
        decision=parsed.get("decision", ""),
        confidence=parsed.get("confidence", ""),
        response_text=_combine_feedback_text(parsed),
        thumbs=thumbs,
        user_email=st.session_state.get("user_email", ""),
    )
    st.toast("Feedback logged.")


def _render_copyable_section(title, icon, text, empty_message, key):
    with st.container(border=True):
        st.markdown(f"#### {icon} {title}")
        st.markdown(text or empty_message)

        if text:
            with st.expander("Copy as plain text"):
                st.text_area(
                    title,
                    value=text,
                    height=150,
                    disabled=True,
                    label_visibility="collapsed",
                    key=key
                )


def _render_result(parsed, similar):
    is_l1 = "L1" in parsed.get("decision", "").upper()

    _render_decision_banner(is_l1)

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Decision", "L1 Resolvable" if is_l1 else "Escalate to L2+", "AI triage recommendation", "🤖")
    with k2:
        kpi_card("Confidence", parsed.get("confidence") or "N/A", "Model self-assessed", "📊")
    with k3:
        kpi_card("Similar Tickets Used", len(similar), "Retrieved from the ticket index", "🔎")

    _render_copyable_section(
        "Investigation Summary", "🔍",
        parsed.get("investigation_summary", ""),
        "_No investigation summary was generated._",
        "support_triage_investigation_summary_plain"
    )
    _render_copyable_section(
        "Draft Comment — Assignee (Internal)", "🛠️",
        parsed.get("assignee_comment", ""),
        "_No assignee comment was generated._",
        "support_triage_assignee_comment_plain"
    )
    _render_copyable_section(
        "Draft Comment — Reporter (External)", "💬",
        parsed.get("reporter_comment", ""),
        "_No reporter comment was generated._",
        "support_triage_reporter_comment_plain"
    )

    with st.container(border=True):
        st.markdown("#### 🗂️ Similar Past Tickets Used")
        if similar:
            similar_df = pd.DataFrame(similar).rename(columns={
                "ticket_id": "Ticket",
                "escalation_level": "Escalation Level",
                "text": "Summary + Resolution",
            })[["Ticket", "Escalation Level", "Summary + Resolution"]]
            st.dataframe(similar_df, width="stretch", hide_index=True)
        else:
            st.info("No similar past tickets were found in the index for this ticket.")

    with st.container(border=True):
        st.markdown("#### 🗳️ Was this helpful?")
        feedback_cols = st.columns([1, 1, 4])
        with feedback_cols[0]:
            if st.button("👍 Helpful", key="support_triage_thumbs_up", width="stretch"):
                _log_current_feedback(parsed, "up")
        with feedback_cols[1]:
            if st.button("👎 Not quite right", key="support_triage_thumbs_down", width="stretch"):
                _log_current_feedback(parsed, "down")


def render(filtered_df):
    st.title("🤖 Support Triage Agent")
    st.caption(
        "Paste a new ticket to get an L1/escalation recommendation, based on similar resolved KSC tickets."
    )

    stats = get_index_stats()
    index_count = stats["count"]

    status_cols = st.columns([3, 1])
    with status_cols[0]:
        if index_count > 0:
            _render_banner(
                "🟢 Ticket Index Ready",
                f"{index_count} resolved KSC tickets indexed and ready for retrieval.",
                "success"
            )
        else:
            _render_banner(
                "🟠 Ticket Index Empty",
                "Click \"Refresh ticket index\" before triaging a new ticket.",
                "warning"
            )
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

    with st.container(border=True):
        st.markdown("#### ✍️ New Ticket")
        ticket_text = st.text_area(
            "New ticket description",
            height=150,
            placeholder="e.g. User reports login fails after password reset...",
            key="support_triage_ticket_text",
            label_visibility="collapsed"
        )

    with st.container(border=True):
        st.markdown("#### 🔬 Investigation Sources (optional)")
        st.caption("Paste findings or attach a screenshot/file from any of these tools to sharpen the analysis.")

        source_cols = st.columns(3)
        with source_cols[0]:
            es_source = _render_investigation_source_input("Elastic Search", "support_triage_es")
        with source_cols[1]:
            metabase_source = _render_investigation_source_input("Metabase", "support_triage_metabase")
        with source_cols[2]:
            portal_source = _render_investigation_source_input("Operational Portal", "support_triage_portal")

        investigation_sources = [es_source, metabase_source, portal_source]

        if st.button("🚀 Triage Ticket", type="primary"):
            if not ticket_text.strip():
                st.warning("Enter a ticket description before triaging.")
            elif index_count == 0:
                st.warning("The ticket index is empty. Refresh the index before triaging.")
            else:
                with st.spinner("Analyzing against ticket history and investigation findings..."):
                    try:
                        similar = retrieve_similar_tickets(ticket_text)
                        raw_response = triage_ticket(ticket_text, similar, investigation_sources)
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
