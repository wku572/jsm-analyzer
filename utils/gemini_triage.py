import streamlit as st
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types


MODEL = "gemini-3.5-flash"

SYSTEM_PROMPT = """You are a support triage assistant for an L1 support team.
Given a new ticket, similar past tickets (with how they were resolved), and
optionally investigation findings from Elastic Search, Metabase, and/or an
operational portal, decide whether this looks resolvable at L1 or needs
escalation to L2+.

Use any investigation findings provided as the primary evidence for your
analysis - they reflect what was actually found for this specific incident,
which is more reliable than general similarity to past tickets.

Respond in this exact format, all five fields every time regardless of
decision:

DECISION: [L1_RESOLVABLE or ESCALATE]
CONFIDENCE: [High/Medium/Low]
INVESTIGATION_SUMMARY: <synthesize the ticket and any investigation findings
provided - what the evidence shows, in plain terms>
ASSIGNEE_COMMENT: <an internal comment draft for the assignee or next
handler - technical, references the investigation findings and any similar
past tickets by key, appropriate whether resolving or escalating>
REPORTER_COMMENT: <an external-facing comment draft for the reporter - no
internal jargon, log details, or ticket keys. If resolvable, explain the fix
and next steps. If escalating, give an appropriate status update without
overpromising a timeline>
"""


@st.cache_resource
def _get_gemini_client():
    if "GEMINI_API_KEY" not in st.secrets:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to .streamlit/secrets.toml."
        )

    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def _build_investigation_parts(investigation_sources):
    parts = []

    for source in investigation_sources or []:
        label = source.get("label", "Investigation Source")
        text = (source.get("text") or "").strip()

        if text:
            parts.append(f"[{label} findings]\n{text}")

        file_bytes = source.get("file_bytes")
        file_mime = source.get("file_mime")

        if file_bytes and file_mime:
            if file_mime.startswith("image/"):
                parts.append(f"[{label} - attached screenshot below]")
                parts.append(
                    genai_types.Part.from_bytes(data=file_bytes, mime_type=file_mime)
                )
            else:
                try:
                    decoded = file_bytes.decode("utf-8", errors="replace")
                except Exception:
                    decoded = ""
                if decoded.strip():
                    parts.append(f"[{label} - uploaded file contents]\n{decoded}")

    return parts


def triage_ticket(ticket_text, similar_tickets, investigation_sources=None):
    client = _get_gemini_client()

    context = "\n\n".join(
        f"[Past ticket {s['ticket_id']} - resolved at {s['escalation_level']}]\n{s['text']}"
        for s in similar_tickets
    ) or "No similar past tickets were found."

    contents = [f"New ticket:\n{ticket_text}\n\nSimilar past tickets:\n{context}"]

    investigation_parts = _build_investigation_parts(investigation_sources)
    if investigation_parts:
        contents.append("Investigation findings for this ticket:")
        contents.extend(investigation_parts)
    else:
        contents.append("No investigation findings were provided for this ticket.")

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1200,
            # gemini-3.5-flash spends tokens on invisible reasoning by default,
            # which can silently eat the whole max_output_tokens budget before
            # any visible text is produced. Disabled since this task is a
            # straightforward classification, not something needing deep
            # chain-of-thought.
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
        ),
    )

    return response.text


def describe_error(exc):
    if isinstance(exc, genai_errors.APIError):
        status_code = getattr(exc, "code", None)

        if status_code == 401 or status_code == 403:
            return "The Gemini API key is invalid, missing, or lacks access. Check GEMINI_API_KEY in secrets.toml."
        if status_code == 429:
            return "Gemini API rate limit reached. Please wait a moment and try again."
        if status_code == 503:
            return "The Gemini model is temporarily overloaded (high demand). Please try again shortly."
        if status_code == 400:
            return getattr(exc, "message", None) or "Gemini API rejected the request (bad request)."

        return getattr(exc, "message", None) or f"Gemini API returned an error (status {status_code})."

    return "An unexpected error occurred while contacting Gemini."


def parse_triage_response(raw_text):
    parsed = {
        "decision": "",
        "confidence": "",
        "investigation_summary": "",
        "assignee_comment": "",
        "reporter_comment": "",
        # Kept for backward compatibility with feedback rows logged under the
        # older single-comment protocol; the current prompt no longer emits these.
        "draft_response": "",
        "escalation_summary": "",
        "raw_text": raw_text,
    }

    section_markers = {
        "DECISION:": ("decision", False),
        "CONFIDENCE:": ("confidence", False),
        "INVESTIGATION_SUMMARY:": ("investigation_summary", True),
        "ASSIGNEE_COMMENT:": ("assignee_comment", True),
        "REPORTER_COMMENT:": ("reporter_comment", True),
        "DRAFT_RESPONSE:": ("draft_response", True),
        "ESCALATION_SUMMARY:": ("escalation_summary", True),
    }

    current_key = None
    buffer = []

    def flush():
        if current_key and buffer:
            parsed[current_key] = "\n".join(buffer).strip()

    for line in raw_text.splitlines():
        stripped = line.strip()
        matched = False

        for marker, (key, is_multiline) in section_markers.items():
            if stripped.upper().startswith(marker):
                flush()
                value = stripped.split(":", 1)[1].strip()

                if is_multiline:
                    current_key = key
                    buffer = [value]
                else:
                    parsed[key] = value
                    current_key, buffer = None, []

                matched = True
                break

        if not matched and current_key:
            buffer.append(line)

    flush()
    return parsed
