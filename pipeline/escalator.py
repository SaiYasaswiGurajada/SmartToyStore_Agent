"""
pipeline/escalator.py — Email escalation engine.

Implements send-then-confirm (system-guardrails §3):
  compose → send → on success, tell customer and mark customer_informed
                 → on failure, retry 3x with backoff [2, 5, 15]s
                 → on final failure, SEND_FAILED — do NOT claim escalation.

Level 1 NEVER calls this module. Level 2 and 3 only.
"""

from __future__ import annotations
import json
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import (
    LLM_API_KEY, LLM_MODEL,
    GMAIL_SENDER, GMAIL_APP_PASSWORD, SMTP_HOST, SMTP_PORT,
    EMAIL_SEND_RETRIES, EMAIL_RETRY_BACKOFF_SECONDS,
    ESCALATION_HIERARCHY,
)
from pipeline.guardrails_loader import load_system_prompt
from pipeline.db import (
    create_ticket, update_ticket_send, get_existing_ticket,
    get_message_history,
)

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=LLM_API_KEY)
    return _client


# --------------------------------------------------------------------------
# Email composition
# --------------------------------------------------------------------------

def _compose_email(
    session_id: str,
    ticket_id: int,
    level: int,
    trigger_type: str,
    reason_summary: str,
    primary_factors: list,
    is_event_not_question: bool,
    history: list[dict],
    routed_to_label: str,
) -> tuple[str, str]:
    """Returns (subject, body) for the escalation email."""
    skill_text = (Path(__file__).parent.parent / "skills" / "escalation-email-skill.md").read_text()

    # Build transcript (already redacted in DB)
    transcript_lines = []
    for msg in history:
        role = "Customer" if msg.get("sender") == "CUSTOMER" else "Assistant"
        transcript_lines.append(f"[{msg.get('timestamp','')}] {role}: {msg.get('message_text','')}")
    transcript = "\n".join(transcript_lines)

    # Subject
    short_issue = reason_summary[:60].rstrip()
    subject = f"[STS-L{level}] {short_issue} — {session_id[:8]} — Ticket #{ticket_id}"

    # Level 3 header
    l3_header = ""
    if level == 3:
        l3_header = (
            "PRIORITY: HIGH — SAFETY / LEGAL\n"
            f"Reported event: {reason_summary}\n"
            "Product / model (if stated): not stated\n"
            f"Customer advised to stop using the toy: {'yes' if is_event_not_question else 'no'}\n"
            "Child involved: not stated\n"
            "Action required: acknowledge immediately.\n\n"
        )

    # Body
    factors_str = ", ".join(primary_factors) if primary_factors else "n/a"
    body_parts = [
        l3_header,
        f"=== WHAT HAPPENED ===\n{reason_summary}\n",
        f"=== WHY IT ESCALATED ===\nTrigger: {trigger_type} | Factors: {factors_str}\n",
        f"=== WHAT THE CUSTOMER NEEDS ===\nPlease review the transcript and follow up with the customer.\n",
    ]

    # Suggested reply — omitted for Level 3
    if level < 3:
        body_parts.append(
            "=== SUGGESTED REPLY (draft — not auto-sent) ===\n"
            "\"Thank you for reaching out. We apologise for the inconvenience and "
            "will look into this as soon as possible. A member of our team will be in touch shortly.\"\n"
        )

    body_parts += [
        f"=== FULL TRANSCRIPT ===\n{transcript}\n",
        f"=== METADATA ===\n"
        f"Ticket ID: {ticket_id}\n"
        f"Session ID: {session_id}\n"
        f"Level: {level}\n"
        f"Trigger Type: {trigger_type}\n"
        f"Routed To: {routed_to_label}\n",
    ]

    body = "\n".join(body_parts)
    return subject, body


# --------------------------------------------------------------------------
# SMTP send with retry
# --------------------------------------------------------------------------

def _send_smtp(to_email: str, subject: str, body: str) -> None:
    """Send via Gmail SMTP. Raises on failure."""
    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_SENDER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, to_email, msg.as_string())


def _send_with_retry(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """
    Returns (success, error_message).
    Retries up to EMAIL_SEND_RETRIES times with EMAIL_RETRY_BACKOFF_SECONDS.
    """
    last_error = ""
    for attempt, backoff in enumerate(EMAIL_RETRY_BACKOFF_SECONDS, start=1):
        try:
            _send_smtp(to_email, subject, body)
            return True, ""
        except Exception as e:
            last_error = str(e)
            if attempt < EMAIL_SEND_RETRIES:
                time.sleep(backoff)

    return False, last_error


# --------------------------------------------------------------------------
# Public escalation function
# --------------------------------------------------------------------------

def escalate(
    session_id: str,
    level: int,
    assessment: dict,
    history: list[dict],
) -> dict:
    """
    Orchestrate escalation for level 2 or 3:
      1. Deduplication check
      2. Create ticket (PENDING)
      3. Compose email
      4. Send with retry
      5. Update ticket status
      6. Return result dict with {success, ticket_id, customer_message}

    Never tells the customer the escalation succeeded until send is confirmed.
    """
    if level == 1:
        raise ValueError("Escalator called for Level 1 — this is a bug.")

    hierarchy = ESCALATION_HIERARCHY.get(level, {})
    routed_to_email = hierarchy.get("email") or ""
    routed_to_label = hierarchy.get("label", f"Level {level}")

    # Deduplication: one email per session per level
    existing = get_existing_ticket(session_id, level)
    if existing and existing["send_status"] == "SENT":
        # Already sent at this level — return the old ticket info
        return {
            "success": True,
            "ticket_id": existing["ticket_id"],
            "already_sent": True,
            "customer_message": _customer_message(level, existing["ticket_id"], sent=True),
        }

    # Create the ticket (PENDING)
    ticket_id = create_ticket(
        session_id=session_id,
        level=level,
        trigger_type=assessment.get("trigger_type", "GENERAL"),
        is_event_not_question=bool(assessment.get("is_event_not_question", False)),
        primary_factors=str(assessment.get("primary_factors", [])),
        routed_to_label=routed_to_label,
        routed_to_email=routed_to_email or "not-configured",
        reason_summary=assessment.get("reason_summary", ""),
    )

    # Compose email
    subject, body = _compose_email(
        session_id=session_id,
        ticket_id=ticket_id,
        level=level,
        trigger_type=assessment.get("trigger_type", "GENERAL"),
        reason_summary=assessment.get("reason_summary", ""),
        primary_factors=assessment.get("primary_factors", []),
        is_event_not_question=bool(assessment.get("is_event_not_question", False)),
        history=history,
        routed_to_label=routed_to_label,
    )

    # Send (skip if no email configured — mark as SEND_FAILED for operator)
    if not routed_to_email or not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        update_ticket_send(ticket_id, "SEND_FAILED",
                           error="Email not configured",
                           customer_informed=0, attempts=1)
        return {
            "success": False,
            "ticket_id": ticket_id,
            "already_sent": False,
            "customer_message": (
                "I've flagged this for our team and someone will be in touch with you directly."
            ),
        }

    success, error = _send_with_retry(routed_to_email, subject, body)

    if success:
        update_ticket_send(ticket_id, "SENT",
                           customer_informed=1,
                           attempts=len(EMAIL_RETRY_BACKOFF_SECONDS))
        return {
            "success": True,
            "ticket_id": ticket_id,
            "already_sent": False,
            "customer_message": _customer_message(level, ticket_id, sent=True),
        }
    else:
        update_ticket_send(ticket_id, "SEND_FAILED",
                           error=error, customer_informed=0,
                           attempts=len(EMAIL_RETRY_BACKOFF_SECONDS))
        # Per spec: do NOT claim escalation happened
        return {
            "success": False,
            "ticket_id": ticket_id,
            "already_sent": False,
            "customer_message": (
                "I've flagged this and someone from our team will be in touch with you directly."
            ),
        }


def _customer_message(level: int, ticket_id: int, sent: bool) -> str:
    """
    Return the customer-facing escalation notice.
    Never states the level number or the recipient's name/role.
    """
    ref = f"(Ref: STS-{ticket_id:04d})"
    if level == 3:
        return (
            f"I've passed this on to our team as a top priority. "
            f"Someone will be in touch with you very soon. {ref}"
        )
    return (
        f"I've passed your details on and someone from our team "
        f"will follow up with you shortly. {ref}"
    )
