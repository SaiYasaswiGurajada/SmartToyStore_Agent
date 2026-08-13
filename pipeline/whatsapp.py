"""
pipeline/whatsapp.py — Twilio WhatsApp webhook handler.

Spec requirements:
  - Accepts application/x-www-form-urlencoded (NOT JSON)
  - Validates X-Twilio-Signature
  - Returns empty TwiML in <500ms
  - Runs generation in BackgroundTask
  - Checks MessageSid for deduplication
  - Fetches media with Basic auth → data/media/
  - Explicitly declines audio
"""

from __future__ import annotations
from typing import Optional
import os
import hashlib
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM,
    PUBLIC_WEBHOOK_URL, TWILIO_VALIDATE_SIGNATURE,
    WA_MEDIA_DIR, WA_ALLOWED_MEDIA_TYPES,
)
from pipeline.db import (
    is_message_processed, mark_message_processed,
    log_message,
)
from pipeline.responder import process_turn

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


# --------------------------------------------------------------------------
# Signature validation
# --------------------------------------------------------------------------

def validate_signature(url: str, params: dict, signature: str) -> bool:
    """Validate X-Twilio-Signature. Returns True if valid or validation is disabled."""
    if not TWILIO_VALIDATE_SIGNATURE:
        return True
    if not TWILIO_AUTH_TOKEN:
        return False
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        return validator.validate(url, params, signature)
    except Exception:
        return False


# --------------------------------------------------------------------------
# Media fetching
# --------------------------------------------------------------------------

def _fetch_media(url: str, content_type: str, session_id: str) -> Optional[str]:
    """Download media from Twilio URL (requires Basic auth) → local path."""
    if content_type not in WA_ALLOWED_MEDIA_TYPES:
        return None
    try:
        import requests
        resp = requests.get(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        resp.raise_for_status()
        ext = content_type.split("/")[-1].replace("jpeg", "jpg")
        filename = f"{session_id[:8]}_{uuid.uuid4().hex[:8]}.{ext}"
        local_path = WA_MEDIA_DIR / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(resp.content)
        return str(local_path)
    except Exception as e:
        print(f"[whatsapp] Media fetch failed: {e}")
        return None


# --------------------------------------------------------------------------
# Session ID for WhatsApp (keyed by WaId)
# --------------------------------------------------------------------------

def wa_session_id(wa_id: str) -> str:
    """Derive a stable session_id from the WaId."""
    return "wa_" + hashlib.md5(wa_id.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# Parse Twilio webhook payload
# --------------------------------------------------------------------------

def parse_payload(form_data: dict) -> dict:
    """
    Normalise the Twilio form payload into a standard message dict.
    Fields: MessageSid, From, To, Body, ProfileName, WaId, NumMedia, MediaUrl0..N
    """
    num_media = int(form_data.get("NumMedia", "0") or 0)
    media_items = []
    for i in range(num_media):
        url = form_data.get(f"MediaUrl{i}", "")
        content_type = form_data.get(f"MediaContentType{i}", "")
        if url:
            media_items.append({"url": url, "content_type": content_type})

    return {
        "message_sid": form_data.get("MessageSid", ""),
        "from_number": form_data.get("From", ""),
        "to_number": form_data.get("To", ""),
        "body": form_data.get("Body", "").strip(),
        "profile_name": form_data.get("ProfileName", ""),
        "wa_id": form_data.get("WaId", ""),
        "media": media_items,
    }


# --------------------------------------------------------------------------
# Send reply via Twilio REST
# --------------------------------------------------------------------------

def send_whatsapp_reply(to: str, body: str) -> bool:
    """Send an outbound WhatsApp message via Twilio REST API."""
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to,
            body=body,
        )
        return True
    except Exception as e:
        print(f"[whatsapp] Send failed: {e}")
        return False


# --------------------------------------------------------------------------
# Main background processing function
# --------------------------------------------------------------------------

def process_whatsapp_message(payload: dict) -> None:
    """
    Full generation pipeline for a WhatsApp message.
    Called in a BackgroundTask so the webhook returns empty TwiML first.
    """
    message_sid = payload["message_sid"]
    wa_id = payload["wa_id"]
    from_number = payload["from_number"]
    profile_name = payload["profile_name"]
    body = payload["body"]
    media_items = payload["media"]

    # Deduplication
    session_id = wa_session_id(wa_id)
    if is_message_processed(message_sid):
        return
    mark_message_processed(message_sid, session_id)

    # Handle audio: decline explicitly
    for item in media_items:
        if item["content_type"].startswith("audio/"):
            reply = (
                "I can't listen to audio messages — please type your question "
                "and I'll be happy to help."
            )
            send_whatsapp_reply(from_number, reply)
            log_message(session_id, "ASSISTANT", reply, action_taken="DECLINE_SCOPE")
            return

    # Fetch allowed media
    media_note = ""
    for item in media_items:
        local_path = _fetch_media(item["url"], item["content_type"], session_id)
        if local_path:
            media_note += f"\n[Media attached: {item['content_type']}]"
        else:
            media_note += f"\n[Media type {item['content_type']} not supported]"

    # Build effective message
    effective_body = body
    if not effective_body and media_items:
        effective_body = "[Customer sent media only]"
    if media_note:
        effective_body = effective_body + media_note

    if not effective_body:
        return

    # Process through the main pipeline
    result = process_turn(
        raw_message=effective_body,
        session_id=session_id,
        channel="whatsapp",
        wa_id=wa_id,
        profile_name=profile_name,
    )

    # Send the reply
    send_whatsapp_reply(from_number, result["text"])
