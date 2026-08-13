"""
pipeline/safety.py — Deterministic Level 3 safety floor.

final_level = max(model_assessed_level, safety_floor_level)

The floor can only raise a level, never lower it.
Consults the model's is_event_not_question flag before firing on hypotheticals.
"""

from __future__ import annotations
import re

# --------------------------------------------------------------------------
# Keyword lists (from safety-floor-rules.md)
# --------------------------------------------------------------------------

INJURY_VOCAB: set[str] = {
    "choke", "choked", "choking",
    "swallow", "swallowed",
    "shock", "shocked", "electrocuted",
    "burn", "burnt", "burned",
    "fire", "caught fire",
    "smoke", "smoking",
    "melting", "melted",
    "overheat", "overheating",
    "sparking", "sparks",
    "allergic", "allergic reaction", "rash",
    "hospital", "emergency",
    "bleeding", "injured", "injury",
    "hurt", "cut",
}

LEGAL_VOCAB: set[str] = {
    "lawyer", "advocate",
    "legal notice", "sue", "suing",
    "court", "consumer court", "consumer forum",
    "consumer safety authority",
    "reporting this", "complaint to authorities", "fir",
}


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def _contains_any(text_norm: str, vocab: set[str]) -> bool:
    for phrase in vocab:
        # Use word-boundary matching for single-word terms
        if " " in phrase:
            if phrase in text_norm:
                return True
        else:
            if re.search(rf"\b{re.escape(phrase)}\b", text_norm):
                return True
    return False


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def keyword_floor(text: str) -> int:
    """
    Returns 3 if safety or legal vocabulary is present, else 1.
    Does NOT yet check is_event_not_question — that's done in apply_floor().
    """
    norm = _normalise(text)
    if _contains_any(norm, INJURY_VOCAB) or _contains_any(norm, LEGAL_VOCAB):
        return 3
    return 1


def apply_floor(
    model_level: int,
    text: str,
    is_event_not_question: bool,
) -> int:
    """
    Compute: final_level = max(model_level, safety_floor_level).

    The floor fires on safety/legal vocabulary BUT only when the model
    determined this is an actual event (is_event_not_question=True).
    Hypothetical questions ("what happens if it catches fire") stay at
    whatever level the model assessed.
    """
    raw_floor = keyword_floor(text)

    if raw_floor == 3 and not is_event_not_question:
        # Hypothetical / second-hand — floor does NOT fire
        raw_floor = 1

    return max(model_level, raw_floor)
