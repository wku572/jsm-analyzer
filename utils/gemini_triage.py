import streamlit as st
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types


MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """You are a support triage assistant for an L1 support team.
Given a new ticket and similar past tickets (with how they were resolved),
decide whether this looks resolvable at L1 or needs escalation to L2+.

Respond in this exact format:

DECISION: [L1_RESOLVABLE or ESCALATE]
CONFIDENCE: [High/Medium/Low]

If L1_RESOLVABLE:
DRAFT_RESPONSE: <a suggested reply to the customer/reporter>

If ESCALATE:
ESCALATION_SUMMARY: <what's known, what's been tried, why it needs L2, and
which similar past tickets support that>
"""


@st.cache_resource
def _get_gemini_client():
    if "GEMINI_API_KEY" not in st.secrets:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Add it to .streamlit/secrets.toml."
        )

    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def triage_ticket(ticket_text, similar_tickets):
    client = _get_gemini_client()

    context = "\n\n".join(
        f"[Past ticket {s['ticket_id']} - resolved at {s['escalation_level']}]\n{s['text']}"
        for s in similar_tickets
    ) or "No similar past tickets were found."

    response = client.models.generate_content(
        model=MODEL,
        contents=f"New ticket:\n{ticket_text}\n\nSimilar past tickets:\n{context}",
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=600,
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
        if status_code == 400:
            return getattr(exc, "message", None) or "Gemini API rejected the request (bad request)."

        return getattr(exc, "message", None) or f"Gemini API returned an error (status {status_code})."

    return "An unexpected error occurred while contacting Gemini."


def parse_triage_response(raw_text):
    parsed = {
        "decision": "",
        "confidence": "",
        "draft_response": "",
        "escalation_summary": "",
        "raw_text": raw_text,
    }

    current_key = None
    buffer = []

    def flush():
        if current_key and buffer:
            parsed[current_key] = "\n".join(buffer).strip()

    for line in raw_text.splitlines():
        stripped = line.strip()

        if stripped.upper().startswith("DECISION:"):
            flush()
            parsed["decision"] = stripped.split(":", 1)[1].strip()
            current_key, buffer = None, []
        elif stripped.upper().startswith("CONFIDENCE:"):
            flush()
            parsed["confidence"] = stripped.split(":", 1)[1].strip()
            current_key, buffer = None, []
        elif stripped.upper().startswith("DRAFT_RESPONSE:"):
            flush()
            current_key = "draft_response"
            buffer = [stripped.split(":", 1)[1].strip()]
        elif stripped.upper().startswith("ESCALATION_SUMMARY:"):
            flush()
            current_key = "escalation_summary"
            buffer = [stripped.split(":", 1)[1].strip()]
        elif current_key:
            buffer.append(line)

    flush()
    return parsed
