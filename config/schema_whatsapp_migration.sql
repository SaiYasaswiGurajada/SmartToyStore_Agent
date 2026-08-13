-- WhatsApp channel migration.
-- Apply AFTER schema.sql. Additive only; nothing in the original four tables changes shape.

PRAGMA foreign_keys = ON;

-- Channel identity on the session -----------------------------------------
ALTER TABLE chat_sessions ADD COLUMN channel          TEXT DEFAULT 'web';
ALTER TABLE chat_sessions ADD COLUMN wa_id            TEXT;
ALTER TABLE chat_sessions ADD COLUMN profile_name     TEXT;
-- drives the 24-hour service window check on human follow-ups
ALTER TABLE chat_sessions ADD COLUMN last_inbound_at  TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_sessions_wa_id ON chat_sessions(wa_id);

-- Idempotency -------------------------------------------------------------
-- Twilio re-delivers on a slow or failed webhook, and Meta retries
-- aggressively. Without this, one retry sends a second escalation email and
-- the deduplication in the escalation engine is bypassed entirely.
CREATE TABLE IF NOT EXISTS processed_messages (
    provider_message_id TEXT PRIMARY KEY,   -- Twilio MessageSid
    session_id          TEXT,
    received_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Outbound log ------------------------------------------------------------
-- Lets a missing reply be traced to a send failure rather than a
-- generation failure.
CREATE TABLE IF NOT EXISTS outbound_messages (
    outbound_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    provider_message_id TEXT,
    body                TEXT,
    send_status         TEXT DEFAULT 'QUEUED'
                        CHECK (send_status IN ('QUEUED','SENT','DELIVERED','FAILED')),
    error_code          TEXT,
    sent_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

-- Inbound media -----------------------------------------------------------
-- Damage claims need photographs. WhatsApp makes that natural; the web
-- version could not do it at all.
CREATE TABLE IF NOT EXISTS inbound_media (
    media_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    message_id          INTEGER,
    provider_media_url  TEXT NOT NULL,
    content_type        TEXT,
    local_path          TEXT,
    fetched             INTEGER DEFAULT 0,
    received_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
    FOREIGN KEY (message_id) REFERENCES message_history(message_id)
);

CREATE INDEX IF NOT EXISTS idx_media_session ON inbound_media(session_id);

-- Sessions with more than one escalation email: should return no rows.
-- Run this after every test pass.
--
--   SELECT session_id, COUNT(*) AS emails
--   FROM escalation_tickets
--   GROUP BY session_id
--   HAVING COUNT(*) > 1;
