"""
pipeline/menu.py — Greeting-driven menu navigation.

Rules (from menu-navigation-skill.md and KB §9):
  - Greeting-ONLY message → show fixed hardcoded 5-option menu.
  - "Hi, my toy won't pair" → NOT a greeting → answer directly.
  - Submenu selection → look up KB subsection via menu_map.json.
  - Free text while menu open → drop menu, answer question.
  - Safety report mid-menu → escalate immediately (handled in responder).
  - Menu state stored on session, cleared on free-text answer or escalation.
"""

from __future__ import annotations
from typing import Optional
import json
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import MENU_MAP

_menu_config: Optional[dict] = None


def _load_menu() -> dict:
    global _menu_config
    if _menu_config is None:
        _menu_config = json.loads(Path(MENU_MAP).read_text(encoding="utf-8"))
    return _menu_config


# --------------------------------------------------------------------------
# Fixed hardcoded menu text (spec: never generated)
# --------------------------------------------------------------------------

MAIN_MENU_TEXT = (
    "Hello! 👋 I'm here to help with anything about your smart toy.\n"
    "Choose a topic to get started, or just type your question anytime:\n\n"
    "1. Connectivity & Setup\n"
    "2. Features & How It Works\n"
    "3. Battery & Maintenance\n"
    "4. Pricing & Discounts\n"
    "5. Orders, Delivery, Warranty & Safety"
)

MAIN_MENU_OPTIONS = [
    {"id": "1", "label": "Connectivity & Setup"},
    {"id": "2", "label": "Features & How It Works"},
    {"id": "3", "label": "Battery & Maintenance"},
    {"id": "4", "label": "Pricing & Discounts"},
    {"id": "5", "label": "Orders, Delivery, Warranty & Safety"},
]


def _get_submenu_items(parent_id: str) -> list[dict] | None:
    cfg = _load_menu()
    for section in cfg["menu"]:
        if section["id"] == parent_id:
            return section["items"]
    return None


def _submenu_text(parent_id: str, items: list[dict]) -> str:
    label_map = {s["id"]: s["label"] for s in _load_menu()["menu"]}
    label = label_map.get(parent_id, f"Topic {parent_id}")
    lines = [f"📋 {label}:"]
    for item in items:
        lines.append(f"  {item['id']}. {item['prompt']}")
    lines.append("\nOr just type your question anytime.")
    return "\n".join(lines)


def _submenu_options(items: list[dict]) -> list[dict]:
    return [{"id": item["id"], "label": item["prompt"]} for item in items]


# --------------------------------------------------------------------------
# Greeting detection
# --------------------------------------------------------------------------

_GREETING_RE = re.compile(
    r"^(hi+|hello+|hey+|hlo+|hii+|namaste|good\s+(morning|evening|afternoon|day))[\s!.]*$",
    re.IGNORECASE,
)


def is_greeting_only(text: str) -> bool:
    """True only if the entire message is a greeting with no question attached."""
    return bool(_GREETING_RE.match(text.strip()))


# --------------------------------------------------------------------------
# Menu input classifier
# --------------------------------------------------------------------------

_MENU_NUMBER_RE = re.compile(r"^\s*(\d+)(?:\.(\d+))?\s*$")


def classify_menu_input(text: str, current_position: Optional[str]) -> dict:
    """
    Returns a dict:
      {
        "type": "greeting" | "main_number" | "sub_number" | "free_text",
        "main": Optional[str],
        "sub": Optional[str],
        "kb_section": Optional[str],  # e.g. "2.1"
      }
    """
    stripped = text.strip()

    if is_greeting_only(stripped):
        return {"type": "greeting", "main": None, "sub": None, "kb_section": None}

    m = _MENU_NUMBER_RE.match(stripped)
    if m:
        main_id = m.group(1)
        sub_id = m.group(2)

        if sub_id:
            # e.g. "1.3" — submenu item
            full_id = f"{main_id}.{sub_id}"
            kb_section = _resolve_kb_section(main_id, full_id)
            return {"type": "sub_number", "main": main_id, "sub": full_id,
                    "kb_section": kb_section}

        # Just a top-level number
        if current_position and "." not in current_position:
            # We're at a submenu level — this might be a sub-item shorthand
            full_id = f"{current_position}.{main_id}"
            kb_section = _resolve_kb_section(current_position, full_id)
            if kb_section:
                return {"type": "sub_number", "main": current_position,
                        "sub": full_id, "kb_section": kb_section}

        # Top-level menu selection
        items = _get_submenu_items(main_id)
        if items:
            return {"type": "main_number", "main": main_id, "sub": None,
                    "kb_section": None}

    return {"type": "free_text", "main": None, "sub": None, "kb_section": None}


def _resolve_kb_section(main_id: str, full_id: str) -> Optional[str]:
    """Look up which KB subsection a menu item maps to."""
    cfg = _load_menu()
    for section in cfg["menu"]:
        if section["id"] == main_id:
            for item in section["items"]:
                if item["id"] == full_id:
                    return item.get("kb", None)
    return None


# --------------------------------------------------------------------------
# Menu response builders
# --------------------------------------------------------------------------

def build_main_menu_response() -> dict:
    return {
        "text": MAIN_MENU_TEXT,
        "options": MAIN_MENU_OPTIONS,
        "new_menu_position": None,  # not inside a category yet
    }


def build_submenu_response(main_id: str) -> Optional[dict]:
    items = _get_submenu_items(main_id)
    if not items:
        return None
    return {
        "text": _submenu_text(main_id, items),
        "options": _submenu_options(items),
        "new_menu_position": main_id,
    }


def get_submenu_prompt(full_id: str, main_id: str) -> Optional[str]:
    """Return the natural-language prompt for a submenu item (used as the RAG query)."""
    cfg = _load_menu()
    for section in cfg["menu"]:
        if section["id"] == main_id:
            for item in section["items"]:
                if item["id"] == full_id:
                    return item.get("prompt")
    return None
