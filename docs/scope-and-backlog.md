# Scope and Backlog

## In scope

Web chat and WhatsApp channels · document upload for `.md`, `.pdf`, `.txt`, `.docx` · subsection chunking of KB sections 1–7 · two-stage confidence with placeholder rejection · greeting menu with submenu mapping · Level 1 console-and-resolve · three-level seriousness assessment · deterministic Level 3 safety floor · send-then-confirm escalation with retries · PII redaction before write · separate guardrail violation log · rate limiting · SQLite persistence · knowledge gap logging and content report · 60-case golden suite with confusion matrix.

## Deliberately excluded

| Excluded | Reason | Consequence |
|---|---|---|
| Live order lookup | A mocked order database demonstrates nothing and hides the interesting behaviour | "Where is my order" escalates at Level 2 — correct behaviour, not a gap |
| Account system and authentication | Not what the project is assessed on, and a meaningful build in itself | Sessions anonymous; name collected conversationally if offered |
| Payment handling | Never appropriate in a chat surface, and doubly so where children may type | Card details are declined and redacted |
| Reliable age verification | Cannot be done from text, and a false negative is worse than none | Protective defaults applied to everyone instead |
| Voice note transcription | Needs speech-to-text and raises child-voice data questions the privacy guardrail would have to answer first | Voice notes declined explicitly, never silently ignored |
| Reply-ingestion loop | Valuable but needs IMAP polling and thread matching | Loop closes outside the system. First backlog item |
| Multi-tenancy | One store is enough to demonstrate the architecture | Single corpus, single hierarchy |
| Fine-tuning | Prompt and retrieval design carry the behaviour | — |
| Vision analysis of uploaded photos | Storing and forwarding is what a defect claim actually needs | Photos attached to the escalation, not interpreted |

## Backlog, in priority order

1. **Fill the placeholders.** Not a feature, but the highest-value item on the list — it is currently suppressing the entire pricing, delivery and warranty answer surface.
2. **Reply-ingestion loop.** Manager or owner replies to the escalation email; IMAP polling matches the ticket ID and returns the reply to the customer's thread.
3. **Escalation acknowledgement SLA tracking.** Level 3 requires immediate acknowledgement; nothing currently measures whether it happened.
4. **Conflicting-source detection.** Where two subsections disagree, flag to the owner instead of picking a side.
5. **Multilingual.** Customer writes in Hindi or Marathi, bot replies in kind, escalation email stays English.
6. **Voice note transcription**, with the privacy question answered first.
7. **Owner console.** Gap report, ticket queue with send status, violation review, corpus version and re-index.
8. **Separate retrieval evaluation.** Recall@k measured independently so retrieval failures can be distinguished from generation failures.
