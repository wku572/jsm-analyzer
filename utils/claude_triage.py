import streamlit as st
import anthropic


MODEL = "claude-haiku-4-5-20251001"

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
def _get_claude_client():
    if "ANTHROPIC_API_KEY" not in st.secrets:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. Add it to .streamlit/secrets.toml."
        )

    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def triage_ticket(ticket_text, similar_tickets):
    client = _get_claude_client()

    context = "\n\n".join(
        f"[Past ticket {s['ticket_id']} - resolved at {s['escalation_level']}]\n{s['text']}"
        for s in similar_tickets
    ) or "No similar past tickets were found."

    message = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"New ticket:\n{ticket_text}\n\nSimilar past tickets:\n{context}",
            }
        ],
    )

    return message.content[0].text


def describe_error(exc):
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 401:
            return "The Claude API key is invalid or missing. Check ANTHROPIC_API_KEY in secrets.toml."
        if exc.status_code == 429:
            return "Claude API rate limit reached. Please wait a moment and try again."

        message = None
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            message = body.get("error", {}).get("message")

        if exc.status_code == 400 and message and "credit balance" in message.lower():
            return "The Anthropic account is out of API credits. Add credits at console.anthropic.com, then try again."

        return message or f"Claude API returned an error (status {exc.status_code})."

    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the Claude API. Check your network connection and try again."

    return "An unexpected error occurred while contacting Claude."


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
