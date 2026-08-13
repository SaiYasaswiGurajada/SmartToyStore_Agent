---
name: escalation-email
description: Composes the escalation email for Levels 2 and 3, and enforces the rule that the customer is told about the escalation only after the send succeeds.
---

# Role

Write the internal email for a Level 2 or Level 3 escalation. **Level 1 never produces an email** — it is consoled and resolved in chat.

# Send-then-confirm

System-guardrails §3 is unambiguous: never tell the customer something has been escalated unless the email actually sent.

Order of operations:

1. Assess the level.
2. Compose and send.
3. On success → confirm to the customer, record the ticket.
4. On failure → retry with backoff (3 attempts). Log the error.
5. On final failure → **do not claim escalation.** Say a person will be in touch and record the ticket as `SEND_FAILED` for operator pickup.

A cheerful "this has been escalated!" over a failed send is the worst outcome in the system: the customer stops chasing and nobody was told.

# Subject

```
[STS-L{level}] {short issue} — {customer name or session id} — Ticket #{ticket_id}
```

Example: `[STS-L3] Reported minor electric shock, exposed wiring — Ticket #204`

# Body order

1. **What happened** — two sentences, plain.
2. **Why it escalated** — trigger type and the specific factors identified.
3. **What the customer needs** — the concrete ask.
4. **Suggested reply** — a short editable draft, clearly labelled. Never auto-sent. **Omitted entirely for Level 3** — no reply goes out until the owner has reviewed.
5. **Full transcript** — verbatim, unedited, redacted per system-guardrails §6.
6. **Metadata** — ticket ID, session ID, level, trigger type, retrieval confidence, KB subsections retrieved, timestamp.

# Level 3 header

Prepend:

```
PRIORITY: HIGH — SAFETY / LEGAL
Reported event: ...
Product / model (if stated): ...
Customer advised to stop using the toy: yes / no
Child involved: yes / no / not stated
Action required: acknowledge immediately.
```

# Privacy

Per system-guardrails §6, include only what the escalation needs: name or order ID if given, transcript, timestamp. **Never payment details.** Anything redacted in the transcript stays redacted in the email — no unmasked copy anywhere.

# Rules

- One email per issue per session. If the level rises from 2 to 3, send a follow-up prefixed `[ESCALATED FROM L2]` referencing the same ticket.
- Neutral and factual. No editorialising about the customer, no speculation about cause, no blame.
- Never include content from a different session.
