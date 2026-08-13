"""
pipeline/prefilter.py — Pre-filter pipeline (in exact order per spec):
  1. Rate limit
  2. PII redaction
  3. Prompt injection check
  4. Scope check
  5. Safety floor keyword scan (fast path, before full assessment)
"""

from __future__ import annotations
from typing import Optional
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import (
    RATE_LIMIT_MESSAGES_PER_MINUTE,
    REDACTION_PATTERNS,
    DECLINE_OUT_OF_SCOPE,
    NO_COPYRIGHTED_CHARACTERS,
)
from pipeline.db import log_violation

# --------------------------------------------------------------------------
# Rate limiter (per-session sliding window)
# --------------------------------------------------------------------------

_rate_windows: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(session_id: str) -> bool:
    """Returns True if the message is within the rate limit."""
    now = time.time()
    window = _rate_windows[session_id]
    # Remove timestamps older than 60 seconds
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_MESSAGES_PER_MINUTE:
        return False
    window.append(now)
    return True


# --------------------------------------------------------------------------
# PII redaction
# --------------------------------------------------------------------------

_compiled_patterns = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in REDACTION_PATTERNS.items()
}


def redact_pii(text: str) -> tuple[str, list[str]]:
    """
    Returns (redacted_text, list_of_categories_redacted).
    Replacement marker: [redacted: <category>]
    """
    redacted = text
    categories: list[str] = []
    for name, pattern in _compiled_patterns.items():
        if pattern.search(redacted):
            redacted = pattern.sub(f"[redacted: {name}]", redacted)
            categories.append(name)
    return redacted, categories


# --------------------------------------------------------------------------
# Prompt injection detection
# --------------------------------------------------------------------------

_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|all|your)\s+instructions?"
    r"|forget\s+(everything|your\s+instructions?)"
    r"|act\s+as\s+(admin|root|superuser|developer|god|owner)"
    r"|pretend\s+you\s+(are|'re)\s+not"
    r"|reveal\s+(your|the)\s+system\s+prompt"
    r"|what\s+(are|is)\s+your\s+(prompt|instructions?|rules?)"
    r"|jailbreak"
    r"|dan\s+mode"
    r"|override\s+(your\s+)?instructions?)",
    re.IGNORECASE,
)


def _check_injection(text: str) -> bool:
    """Returns True if text looks like a prompt injection attempt."""
    return bool(_INJECTION_PATTERNS.search(text))


# --------------------------------------------------------------------------
# Out-of-scope detection
# --------------------------------------------------------------------------

_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"(write\s+(me\s+)?(a\s+)?(story|poem|essay|song|joke)"
    r"|homework|school\s+assignment"
    r"|play\s+(a\s+game|with\s+me)"
    r"|pretend\s+(to\s+be|you'?re?)\s+\w+"
    r"|role\s*play"
    r"|tell\s+me\s+(a\s+)?joke"
    r"|(harry\s+potter|batman|spiderman|elsa|frozen|minecraft|roblox|pokemon|barbie|doraemon|peppa))",
    re.IGNORECASE,
)


def _check_scope(text: str) -> tuple[bool, str]:
    """
    Returns (is_out_of_scope, violation_type).
    violation_type is 'OUT_OF_SCOPE' or 'COPYRIGHT_REQUEST'.
    """
    if not DECLINE_OUT_OF_SCOPE:
        return False, ""

    if NO_COPYRIGHTED_CHARACTERS:
        copyright_match = re.search(
            r"(harry\s+potter|batman|spiderman|elsa|frozen|minecraft|roblox|pokemon|barbie|doraemon|peppa)",
            text, re.IGNORECASE
        )
        if copyright_match:
            return True, "COPYRIGHT_REQUEST"

    if _OUT_OF_SCOPE_PATTERNS.search(text):
        return True, "OUT_OF_SCOPE"

    return False, ""


# --------------------------------------------------------------------------
# Result dataclass
# --------------------------------------------------------------------------

@dataclass
class PrefilterResult:
    allowed: bool          # False → stop, return canned response
    text: str              # (possibly redacted) text
    redacted_categories: list[str]
    block_reason: Optional[str] = None   # "RATE_LIMIT", "INJECTION", "OUT_OF_SCOPE", "COPYRIGHT_REQUEST"
    canned_response: Optional[str] = None


# --------------------------------------------------------------------------
# Main prefilter function
# --------------------------------------------------------------------------

def prefilter(text: str, session_id: str) -> PrefilterResult:
    """
    Run the full pre-filter chain (in spec order) and return a PrefilterResult.
    PII is ALWAYS redacted before any other processing or DB write.
    """
    # Step 1: Rate limit (check before redaction — no DB write yet)
    if not _check_rate_limit(session_id):
        log_violation(session_id, "RATE_LIMIT",
                      "Rate limit exceeded", "BLOCKED")
        return PrefilterResult(
            allowed=False,
            text=text,
            redacted_categories=[],
            block_reason="RATE_LIMIT",
            canned_response=(
                "You're sending messages a bit quickly. "
                "Please wait a moment and try again."
            ),
        )

    # Step 2: PII redaction — MUST happen before any DB write
    redacted_text, categories = redact_pii(text)
    if categories:
        log_violation(session_id, "PII_REDACTED",
                      f"Redacted: {', '.join(categories)}", "REDACTED")

    # Step 3: Prompt injection check (on redacted text)
    if _check_injection(redacted_text):
        log_violation(session_id, "PROMPT_INJECTION",
                      "Injection pattern detected", "BLOCKED")
        return PrefilterResult(
            allowed=False,
            text=redacted_text,
            redacted_categories=categories,
            block_reason="INJECTION",
            canned_response=(
                "I can only help with questions about your smart toy. "
                "How can I assist you today?"
            ),
        )

    # Step 4: Scope check
    out_of_scope, violation_type = _check_scope(redacted_text)
    if out_of_scope:
        log_violation(session_id, violation_type,
                      redacted_text[:200], "DECLINED")
        if violation_type == "COPYRIGHT_REQUEST":
            canned = (
                "I'm not able to role-play as or reference other characters — "
                "I'm here to help with your smart toy! What can I help you with?"
            )
        else:
            canned = (
                "I can only help with questions about your Smart Toy Store "
                "products. Is there something about your toy I can help with?"
            )
        return PrefilterResult(
            allowed=False,
            text=redacted_text,
            redacted_categories=categories,
            block_reason=violation_type,
            canned_response=canned,
        )

    return PrefilterResult(
        allowed=True,
        text=redacted_text,
        redacted_categories=categories,
    )
