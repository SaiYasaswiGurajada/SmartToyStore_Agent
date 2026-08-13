-- Smart Toy Store Support Assistant — SQLite schema
-- Five tables. Two are not required by the brief: knowledge_gaps exists
-- because gap queries are a content roadmap, and guardrail_violations exists
-- because system-guardrails implementation notes require misuse patterns to be
-- reviewable without mixing them into genuine support data.

PRAGMA foreign_keys = ON;

-- 1. Sessions -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id        TEXT PRIMARY KEY,
    customer_name     TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status            TEXT DEFAULT 'ACTIVE'
                      CHECK (status IN ('ACTIVE','ESCALATED','SAFETY_HOLD','CLOSED')),
    -- highest level already emailed for this session; 0 means none.
    -- Level 1 never sets this, because Level 1 sends no email.
    escalated_level   INTEGER DEFAULT 0 CHECK (escalated_level BETWEEN 0 AND 3),
    -- current menu position, e.g. "4" or "4.2"; cleared on free text and on escalation
    menu_position     TEXT,
    child_signal      INTEGER DEFAULT 0
);

-- 2. Message history ------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_history (
    message_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    sender            TEXT NOT NULL CHECK (sender IN ('CUSTOMER','ASSISTANT','SYSTEM')),
    message_text      TEXT NOT NULL,          -- already redacted
    redaction_applied TEXT,                   -- which categories were masked, never the values
    action_taken      TEXT CHECK (action_taken IN
                          ('MENU','ANSWER','CLARIFY','CONSOLE','ESCALATE','SAFETY_HANDOFF',
                           'DECLINE_SCOPE', NULL)),
    assessed_level    INTEGER CHECK (assessed_level BETWEEN 1 AND 3),
    retrieval_score   REAL,
    evidence_verdict  TEXT,
    grounding_chunks  TEXT,                   -- e.g. "1.1,2.4"
    placeholder_hit   INTEGER DEFAULT 0,
    latency_ms        INTEGER,
    timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

-- 3. Escalation tickets ---------------------------------------------------
-- Level 2 and 3 only. A Level 1 never creates a row here.
CREATE TABLE IF NOT EXISTS escalation_tickets (
    ticket_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    level             INTEGER NOT NULL CHECK (level IN (2,3)),
    trigger_type      TEXT NOT NULL,
    is_event_not_question INTEGER,
    primary_factors   TEXT,
    routed_to_label   TEXT NOT NULL,
    routed_to_email   TEXT NOT NULL,
    reason_summary    TEXT NOT NULL,
    -- system-guardrails 3: the customer is told only once this is SENT
    send_status       TEXT DEFAULT 'PENDING'
                      CHECK (send_status IN ('PENDING','SENT','SEND_FAILED')),
    send_attempts     INTEGER DEFAULT 0,
    send_error        TEXT,
    customer_informed INTEGER DEFAULT 0,
    superseded_by     INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
    FOREIGN KEY (superseded_by) REFERENCES escalation_tickets(ticket_id)
);

-- 4. Knowledge gaps -------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    gap_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    unanswered_query  TEXT NOT NULL,
    similarity_score  REAL,
    evidence_verdict  TEXT,
    nearest_chunk     TEXT,
    placeholder_blocked INTEGER DEFAULT 0,    -- gap caused by an unfilled placeholder
    topic_cluster     TEXT,
    timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

-- 5. Guardrail violations -------------------------------------------------
-- Kept out of message_history so misuse patterns can be reviewed without
-- mixing them into genuine customer support data.
CREATE TABLE IF NOT EXISTS guardrail_violations (
    violation_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT,
    violation_type    TEXT NOT NULL
                      CHECK (violation_type IN
                        ('PROMPT_INJECTION','ABUSE','OUT_OF_SCOPE','PII_REDACTED',
                         'RATE_LIMIT','COPYRIGHT_REQUEST','CHILD_PII_ATTEMPT')),
    detail            TEXT,                   -- description only, never the sensitive value
    action_taken      TEXT,
    timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON message_history(session_id);
CREATE INDEX IF NOT EXISTS idx_tickets_session  ON escalation_tickets(session_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status   ON escalation_tickets(send_status);
CREATE INDEX IF NOT EXISTS idx_gaps_cluster     ON knowledge_gaps(topic_cluster);
CREATE INDEX IF NOT EXISTS idx_violations_type  ON guardrail_violations(violation_type);

-- Checks to run after every test pass:
--
-- Tickets claimed to the customer but never actually sent (must be empty):
--   SELECT * FROM escalation_tickets
--   WHERE customer_informed = 1 AND send_status != 'SENT';
--
-- Level 1 that wrongly produced an email (must be empty by schema, but verify
-- the router never attempts it):
--   SELECT * FROM message_history WHERE assessed_level = 1 AND action_taken = 'ESCALATE';
--
-- Content gap report:
--   SELECT topic_cluster, COUNT(*) AS hits, AVG(similarity_score) AS avg_score
--   FROM knowledge_gaps GROUP BY topic_cluster ORDER BY hits DESC LIMIT 5;
