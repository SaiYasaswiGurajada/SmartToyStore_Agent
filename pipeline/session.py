"""
pipeline/session.py — Session management.

Session key:
  - web channel: generated UUID
  - whatsapp: WaId

Idle timeout: 12 hours (SAFETY_HOLD sessions never expire on a timer).
Child-signal tracking and drift counter live here.
"""

from __future__ import annotations
from typing import Optional
import re
import uuid
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import SESSION_IDLE_TIMEOUT_HOURS, CHILD_SIGNAL_DRIFT_LIMIT
from pipeline.db import (
    get_session, upsert_session, update_session_field, get_message_history,
)

IDLE_SECONDS = SESSION_IDLE_TIMEOUT_HOURS * 3600

# Signals that suggest the person typing may be a child
_CHILD_SIGNAL_RE = re.compile(
    r"(my\s+toy|play\s+with\s+me|can\s+you\s+play|pretend|make\s+believe"
    r"|i\s+want\s+to\s+play|homework|school|teacher|mummy|daddy|papa|mama)",
    re.IGNORECASE,
)


def new_session_id() -> str:
    return str(uuid.uuid4())


def get_or_create_session(
    session_id: str,
    channel: str = "web",
    wa_id: str = None,
    profile_name: str = None,
) -> dict:
    """
    Ensure the session exists in the DB and return a dict of its current state.
    If the session has been idle >12h (and is not SAFETY_HOLD), reset it.
    """
    upsert_session(session_id, channel=channel, wa_id=wa_id,
                   profile_name=profile_name)
    row = get_session(session_id)
    if row is None:
        return _default_state(session_id, channel)

    state = dict(row)

    # Check idle timeout
    if state.get("status") != "SAFETY_HOLD":
        last_active = state.get("last_active_at")
        if last_active and _is_expired(last_active):
            # Reset the session
            update_session_field(
                session_id,
                status="CLOSED",
                menu_position=None,
                escalated_level=0,
            )
            upsert_session(session_id, channel=channel, wa_id=wa_id,
                           profile_name=profile_name)
            return _default_state(session_id, channel)

    return state


def _default_state(session_id: str, channel: str) -> dict:
    return {
        "session_id": session_id,
        "channel": channel,
        "status": "ACTIVE",
        "escalated_level": 0,
        "menu_position": None,
        "child_signal": 0,
    }


def _is_expired(last_active_str: str) -> bool:
    """Parse ISO timestamp string and compare against idle timeout."""
    try:
        import datetime
        if isinstance(last_active_str, str):
            dt = datetime.datetime.fromisoformat(last_active_str.replace("Z", "+00:00"))
        else:
            return False
        now = datetime.datetime.now(datetime.timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return (now - dt).total_seconds() > IDLE_SECONDS
    except Exception:
        return False


def detect_child_signal(text: str) -> bool:
    return bool(_CHILD_SIGNAL_RE.search(text))


def increment_child_drift(session_id: str, current_drift: int) -> int:
    """Increment off-topic turn count; close session warmly at drift limit."""
    new_drift = current_drift + 1
    update_session_field(session_id, child_signal=new_drift)
    return new_drift


def mark_safety_hold(session_id: str) -> None:
    update_session_field(session_id, status="SAFETY_HOLD", menu_position=None)


def mark_escalated(session_id: str, level: int) -> None:
    update_session_field(
        session_id,
        status="ESCALATED",
        escalated_level=level,
        menu_position=None,
    )


def set_menu_position(session_id: str, position: Optional[str]) -> None:
    update_session_field(session_id, menu_position=position)


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    rows = get_message_history(session_id, limit=limit)
    return [dict(r) for r in rows]
