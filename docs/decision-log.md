# Decision Log

Each row records a decision, the alternatives, and the trade-off accepted. The trade-off column is the point — a decision with no cost was not a decision.

| # | Decision | Alternatives | Chosen because | Trade-off accepted |
|---|---|---|---|---|
| 1 | Three levels, with Level 1 sending no email | Four levels as in the generic pattern; every level emails | A toy store has two people worth escalating to. Making Level 1 a resolution path forces the bot to actually solve problems instead of routing frustration | Level 1 quality is now load-bearing; a lazy console reply looks like a working system while helping nobody |
| 2 | Two-stage confidence: similarity, then a structured evidence check | Similarity alone; model self-rating alone | Similarity scores highly on adjacent chunks with no answer. "School discounts?" retrieves §5.3 strongly, and §5.3 only says to contact sales | One extra model call per answered turn |
| 3 | Threshold 0.75, tuned for precision on ANSWER | Balanced F1; tuned for containment | A wrong answer about a child's toy is acted on by a parent. A needless escalation costs a manager minutes. The costs are asymmetric | Containment lower than a balanced setting would give |
| 4 | Safety floor independent of the model, OR'd upward | Model assessment alone; keywords alone | Model judgement fails occasionally and a Level 3 miss is an unreported child injury. Keywords alone cannot separate a hypothetical from an event | False Level 3s reach the CEO. Accepted knowingly |
| 5 | Floor consults the model's event-vs-question classification | Pure keyword match | KB §8.4 requires "what happens if this catches fire" to stay Level 1 while "the toy caught fire" is Level 3. Same vocabulary, different level | The floor is not purely deterministic, so it inherits some model risk. Stated openly rather than papered over |
| 6 | Resolved safety events are not downgraded | Weight the outcome | KB §8.4: "shocked them a little, but they're fine now" is Level 3. The incident determines the level, not how it ended | Some Level 3s turn out to be trivial |
| 7 | Send email, verify, then tell the customer | Reply first, send in background | system-guardrails §3 forbids claiming escalation on a failed send. A false confirmation makes the customer stop chasing while nobody was told | Reply latency includes SMTP time. Mitigated by a 3-attempt retry with backoff |
| 8 | Level 3 is terminal for the session | Reassess each message | A parent who reported an injury must not be returned to automated answering two turns later | Some sessions stay escalated longer than needed |
| 9 | KB sections 8 and 9 excluded from the index | Index the whole document | Both are behaviour specs and say so. Indexed, the bot recites its own escalation logic to a customer — forbidden by system-guardrails §4 | Index build needs section-aware filtering |
| 10 | Placeholder chunks force UNSUPPORTED | Trust that placeholders get filled | An unfilled `[X days]` retrieves at a high score and reads as answer-shaped. Emitting it as policy is worse than escalating | Pricing, delivery and warranty escalate until the placeholders are filled |
| 11 | Protective child-safety defaults applied to everyone | Gate behaviour on age detection | Age cannot be reliably detected from text. Child-signals therefore add restrictions and never relax them | Adults get a slightly more constrained bot |
| 12 | Redaction before any write | Redact at email composition | Redacting at send time means the raw value was already persisted. The only safe point is before the first write | Redaction runs on every message including the vast majority that need none |
| 13 | Guardrail violations in their own table | Log into message_history with a flag | The guardrails doc requires misuse patterns to be reviewable without mixing them into genuine support data | An extra table and a second write path |
| 14 | Menu numbering decoupled from KB numbering | Mirror the KB structure exactly | Menu 4.2 maps to KB §5.2. Decoupling lets the customer-facing structure and the corpus evolve independently | A mapping file to keep in sync |
| 15 | Menu state cleared on free text and on escalation | Persist until explicitly exited | Stale state makes a later bare "3" read as a menu choice rather than a quantity | A customer must re-enter the menu after a free-text detour |
| 16 | Knowledge gaps logged as a first-class table | Log to a file; do not log | Gap queries are a content roadmap for the owner, not just a failure record — and here they also show which placeholders are costing the most | An extra table and a small reporting surface |
| 17 | WhatsApp as the channel, web chat retained | One or the other | WhatsApp is where the customers are; web chat is kept because the brief requires a visible thread, typing indicator and escalation banner, none of which WhatsApp exposes | Two channels, diverging formatting rules |
| 18 | Return the webhook immediately, generate in a background task | Generate inside the request | A slow webhook is re-delivered, and re-delivery sends a duplicate escalation email | Reply arrives as a separate outbound call, needing its own send log |
| 19 | Idempotency on the provider message ID | Rely on session-level dedupe | Session dedupe assumes each message is seen once; a retry is the same message twice and slips underneath it | One extra table and a write per inbound message |

## Threshold tuning record

Fill after running the golden suite. Report all three columns per candidate — a single accuracy number hides the trade-off decision 3 is about.

| Threshold | Containment (L1 resolved + answered) | False-answer rate | False-escalation rate |
|---|---|---|---|
| 0.65 | | | |
| 0.70 | | | |
| 0.75 | | | |
| 0.80 | | | |
