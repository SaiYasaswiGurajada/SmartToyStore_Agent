"""
Smart Toy Store Support Assistant — configuration.

No secrets in this file. Every credential is read from the environment.
Copy .env.example to .env, fill it in, and keep .env out of version control.
"""

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

KB_DIR = ROOT / "kb"
GUARDRAILS_DIR = ROOT / "guardrails"
SKILLS_DIR = ROOT / "skills"
DB_PATH = ROOT / "data" / "smarttoystore.db"

# Read fresh on every turn so editing a markdown file changes behaviour
# without a restart. Behaviour lives in these files, not in Python.
ALWAYS_ON_RULES = [
    GUARDRAILS_DIR / "system-guardrails.md",
    GUARDRAILS_DIR / "grounding-and-confidence.md",
    GUARDRAILS_DIR / "safety-floor-rules.md",
    GUARDRAILS_DIR / "child-safety-rules.md",
]

SKILL_CARDS = {
    "answer": SKILLS_DIR / "rag-answer-skill.md",
    "console": SKILLS_DIR / "console-skill.md",
    "assess": SKILLS_DIR / "seriousness-assessment-skill.md",
    "email": SKILLS_DIR / "escalation-email-skill.md",
    "menu": SKILLS_DIR / "menu-navigation-skill.md",
}

MENU_MAP = ROOT / "config" / "menu_map.json"
HIERARCHY_MAP = ROOT / "config" / "escalation_hierarchy.json"

# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# --------------------------------------------------------------------------
# Escalation hierarchy — THREE levels, and Level 1 sends no email
# --------------------------------------------------------------------------

ESCALATION_HIERARCHY = {
    1: {
        "label": "Bot Console",
        "email": None,
        "sends_email": False,
        "scope": "Console and resolve in chat. Escalate to 2 only if resolution fails.",
    },
    2: {
        "label": "Store Manager",
        "email": os.getenv("EMAIL_MANAGER"),
        "sends_email": True,
        "scope": "Repeated contact, product failure, refund demands, knowledge gaps",
    },
    3: {
        "label": "CEO / Owner",
        "email": os.getenv("EMAIL_OWNER"),
        "sends_email": True,
        "scope": "Any safety event, injury, or legal and regulatory language",
    },
}

SAFETY_FLOOR_LEVEL = 3
LEVEL_3_IS_TERMINAL = True
LEVEL_3_SUPPRESS_TROUBLESHOOTING = True
LEVEL_3_OMIT_SUGGESTED_REPLY = True

# system-guardrails section 3: never claim escalation unless the send succeeded
CONFIRM_ONLY_AFTER_SEND_SUCCESS = True
EMAIL_SEND_RETRIES = 3
EMAIL_RETRY_BACKOFF_SECONDS = [2, 5, 15]

# --------------------------------------------------------------------------
# Retrieval and confidence
# --------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 0.50
TOP_K = 4
CHUNK_STRATEGY = "subsection"          # 1.1, 2.3, 5.2 — per the KB's own notes
CHUNK_ID_PATTERN = r"^###\s+(\d+\.\d+)\s"

# KB sections 8 and 9 are behaviour specs, not retrievable content. Both say so
# explicitly. Indexing them lets the bot recite its own escalation logic to a
# customer, which system-guardrails section 4 forbids.
INDEXABLE_KB_SECTIONS = [1, 2, 3, 4, 5, 6, 7]
EXCLUDED_KB_SECTIONS = [8, 9]

EVIDENCE_SUPPORTED = "SUPPORTED"
EVIDENCE_PARTIAL = "PARTIAL"
EVIDENCE_UNSUPPORTED = "UNSUPPORTED"

# Unfilled placeholders retrieve at a high score and read as answer-shaped
# content. Emitting "[X days]" to a customer is worse than escalating.
PLACEHOLDER_PATTERN = r"\[[^\]]{3,}\]"
REJECT_PLACEHOLDER_CHUNKS = True

MAX_CLARIFICATIONS_PER_TOPIC = 1

# --------------------------------------------------------------------------
# Child safety — system-guardrails section 2
# --------------------------------------------------------------------------

NEVER_REQUEST_PII = True
REDACT_BEFORE_LOGGING = True
REDACTION_PATTERNS = {
    "card": r"\b(?:\d[ -]*?){13,19}\b",
    "cvv": r"\bcvv\s*:?\s*\d{3,4}\b",
    "phone": r"\b(?:\+?91[ -]?)?[6-9]\d{9}\b",
    "email": r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
}
DECLINE_OUT_OF_SCOPE = True            # no stories, games, homework, chit-chat
NO_COPYRIGHTED_CHARACTERS = True
CHILD_SIGNAL_DRIFT_LIMIT = 2           # close warmly after two off-topic turns

# --------------------------------------------------------------------------
# Abuse and rate limiting — system-guardrails section 7
# --------------------------------------------------------------------------

RATE_LIMIT_MESSAGES_PER_MINUTE = 12
RATE_LIMIT_ESCALATIONS_PER_SESSION_PER_HOUR = 3
LOG_GUARDRAIL_VIOLATIONS_SEPARATELY = True   # never mixed with support transcripts

# --------------------------------------------------------------------------
# Channel: WhatsApp
# --------------------------------------------------------------------------

CHANNEL = os.getenv("CHANNEL", "web")          # "web" | "whatsapp" | "both"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
PUBLIC_WEBHOOK_URL = os.getenv("PUBLIC_WEBHOOK_URL")
TWILIO_VALIDATE_SIGNATURE = os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() == "true"

SESSION_IDLE_TIMEOUT_HOURS = 12
CRITICAL_SESSIONS_EXPIRE = False       # a Level 3 session never expires on a timer
SERVICE_WINDOW_HOURS = 24

WA_MAX_BODY_CHARS = 1600
WA_TARGET_CHARS = 700
WA_SPLIT_THRESHOLD = 1500
WA_SUPPORTS_MARKDOWN = False

WA_ACCEPT_MEDIA = True
WA_MEDIA_DIR = ROOT / "data" / "media"
WA_ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
WA_TRANSCRIBE_AUDIO = False

# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".txt", ".docx", ".md"}
MAX_UPLOAD_MB = 20
