"""
pipeline/assess.py — Seriousness assessment via LLM structured output.

Reads the seriousness-assessment skill card fresh each turn.
Returns: level (1/2/3), trigger_type, is_event_not_question, primary_factors, reason_summary.
Applies the safety floor: final_level = max(model_level, floor_level).
"""

from __future__ import annotations
import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import LLM_MODEL
from pipeline.guardrails_loader import load_system_prompt, load_skill
from pipeline.safety import apply_floor

_client = None


def _get_client():
    global _client
    if _client is None:
        import os
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("LLM_API_KEY"))
    return _client


_OUTPUT_SCHEMA = """
Return ONLY a JSON object with these exact keys:
{
  "level": <1|2|3>,
  "trigger_type": "<KNOWLEDGE_GAP|REPEATED_CONTACT|PRODUCT_FAILURE|REFUND_DEMAND|SAFETY_EVENT|LEGAL_THREAT|SARCASM_NEGATIVE|GENERAL>",
  "is_event_not_question": <true|false>,
  "primary_factors": ["..."],
  "reason_summary": "...",
  "confidence": "<high|medium|low>"
}
No other text outside the JSON.
"""


def assess(
    session_id: str,
    user_message: str,
    history: list[dict],
    session_safety_hold: bool = False,
) -> dict:
    """
    Run the seriousness assessment for the current turn.
    Returns a dict with: level, trigger_type, is_event_not_question,
    primary_factors, reason_summary, confidence.
    """
    # If session is already SAFETY_HOLD, level stays 3
    if session_safety_hold:
        return {
            "level": 3,
            "trigger_type": "SAFETY_EVENT",
            "is_event_not_question": True,
            "primary_factors": ["safety_hold_session"],
            "reason_summary": "Session is in SAFETY_HOLD — level stays at 3.",
            "confidence": "high",
        }

    skill_text = load_skill("assess")
    # Use only the assess skill card — loading full guardrails causes 400 token errors
    system_prompt = (
        (skill_text if skill_text else "You are a customer support seriousness assessor for SmartToyStore.")
        + "\n\n---\n\n"
        + _OUTPUT_SCHEMA
    )

    # Build conversation context
    conv_lines = []
    for msg in history[-10:]:  # last 10 turns for context
        role = "Customer" if msg.get("sender") == "CUSTOMER" else "Assistant"
        conv_lines.append(f"{role}: {msg.get('message_text', '')}")
    conv_lines.append(f"Customer: {user_message}")
    conversation = "\n".join(conv_lines)

    user_content = (
        f"Assess the seriousness of the following conversation.\n\n"
        f"Conversation:\n{conversation}"
    )

    try:
        resp = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_completion_tokens=300,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON even if surrounded by markdown fences
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
        else:
            raise ValueError("No JSON found in response")

        model_level = int(data.get("level", 1))
        is_event = bool(data.get("is_event_not_question", False))

        # Apply safety floor
        final_level = apply_floor(model_level, user_message, is_event)
        data["level"] = final_level

        return data

    except Exception as e:
        # Default conservative fallback
        raw_floor = apply_floor(2, user_message, True)
        return {
            "level": raw_floor,
            "trigger_type": "GENERAL",
            "is_event_not_question": False,
            "primary_factors": ["assessment_error"],
            "reason_summary": f"Assessment failed: {e}",
            "confidence": "low",
        }
