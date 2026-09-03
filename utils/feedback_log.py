import csv
import os
from datetime import datetime

import pytz


LOCAL_TZ = "Africa/Addis_Ababa"
FEEDBACK_CSV_PATH = "data/support_triage_feedback.csv"
FEEDBACK_COLUMNS = [
    "timestamp",
    "user_email",
    "ticket_text",
    "decision",
    "confidence",
    "response_text",
    "thumbs",
]


def log_feedback(ticket_text, decision, confidence, response_text, thumbs, user_email):
    os.makedirs(os.path.dirname(FEEDBACK_CSV_PATH), exist_ok=True)

    is_new_file = not os.path.exists(FEEDBACK_CSV_PATH)
    tz = pytz.timezone(LOCAL_TZ)

    with open(FEEDBACK_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if is_new_file:
            writer.writerow(FEEDBACK_COLUMNS)

        writer.writerow([
            datetime.now(tz).isoformat(),
            user_email or "",
            ticket_text or "",
            decision or "",
            confidence or "",
            response_text or "",
            thumbs or "",
        ])
