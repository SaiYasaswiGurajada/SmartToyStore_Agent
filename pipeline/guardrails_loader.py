"""
pipeline/guardrails_loader.py — Loads guardrail and skill markdown files fresh
every turn so editing a rule file changes behaviour without a restart.
"""

from pathlib import Path
from typing import Optional
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config import ALWAYS_ON_RULES, SKILL_CARDS, ROOT

# KB sections 8 and 9 are behaviour specs — not retrievable content.
# They are loaded here into the system prompt instead.
KB_BEHAVIOUR_SECTIONS_FILE = ROOT / "kb" / "smart_toy_store_knowledge_base.md"


def _load_kb_sections_8_9() -> str:
    """Extract sections 8 and 9 from the KB file for system-prompt injection."""
    try:
        text = KB_BEHAVIOUR_SECTIONS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

    # Find section 8 start
    sec8_marker = "## 8."
    sec_end_marker = "\n---\n## Notes"  # ends before the notes section
    start = text.find(sec8_marker)
    if start == -1:
        return ""
    # Grab everything from section 8 to end of section 9
    end = text.find(sec_end_marker, start)
    if end == -1:
        chunk = text[start:]
    else:
        chunk = text[start:end]
    return chunk.strip()


def load_system_prompt(skill_key: Optional[str] = None) -> str:
    """
    Assemble the full system prompt for a turn:
      1. All always-on guardrails (read fresh from disk)
      2. KB sections 8 and 9 (behaviour specs)
      3. The relevant skill card if provided
    """
    parts: list[str] = []

    # 1. Always-on guardrails
    for path in ALWAYS_ON_RULES:
        try:
            parts.append(f"# GUARDRAIL: {Path(path).stem}\n\n{Path(path).read_text(encoding='utf-8')}")
        except FileNotFoundError:
            pass

    # 2. KB sections 8 and 9 — behaviour specs
    behaviour = _load_kb_sections_8_9()
    if behaviour:
        parts.append(f"# ESCALATION AND WORKFLOW SPEC (behaviour only, never quote to customer)\n\n{behaviour}")

    # 3. Skill card
    if skill_key and skill_key in SKILL_CARDS:
        skill_path = Path(SKILL_CARDS[skill_key])
        try:
            parts.append(f"# SKILL: {skill_path.stem}\n\n{skill_path.read_text(encoding='utf-8')}")
        except FileNotFoundError:
            pass

    return "\n\n---\n\n".join(parts)


def load_skill(skill_key: str) -> str:
    """Load just one skill card (used for targeted calls)."""
    if skill_key not in SKILL_CARDS:
        return ""
    path = Path(SKILL_CARDS[skill_key])
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
