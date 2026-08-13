# System Architecture

## Overview

```
   Web chat  ──► POST /api/chat ────────┐
                                        ├──► normalise ──► pipeline
   WhatsApp  ──► POST /webhook/whatsapp ┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
        ┌───────────────────────┐                       ┌───────────────────────┐
        │  Pre-filters (order   │                       │   Retrieval           │
        │  matters)             │                       │  • subsections 1–7    │
        │  1. rate limit        │  runs on every        │  • top K = 4          │
        │  2. PII redaction     │  message, always      │  • S ≥ 0.75           │
        │  3. injection check   │                       │  • placeholder reject │
        │  4. scope check       │                       │  • evidence check     │
        │  5. safety floor scan │                       │                       │
        └───────────┬───────────┘                       └───────────┬───────────┘
                    │                                               │
                    │              ┌────────────────────┐           │
                    └─────────────►│ Seriousness model  │◄──────────┘
                                   │  (whole history)   │
                                   └─────────┬──────────┘
                                             ▼
                              ┌──────────────────────────────┐
                              │  level = max(model, floor)   │
                              └──────────────┬───────────────┘
                                             │
        ┌──────────────┬───────────────┬─────┴──────┬──────────────────┐
        ▼              ▼               ▼            ▼                  ▼
      MENU         ANSWER          CONSOLE      ESCALATE         SAFETY_HANDOFF
    hardcoded     grounded        L1: help,      L2: manager       L3: owner
                                  NO email                        no troubleshooting
                                                  │                     │
                                                  └──────────┬──────────┘
                                                             ▼
                                              ┌──────────────────────────┐
                                              │  Send email FIRST        │
                                              │  retry ×3 with backoff   │
                                              └──────────────┬───────────┘
                                                             ▼
                                              ┌──────────────────────────┐
                                              │ SENT → tell the customer │
                                              │ FAILED → do NOT claim    │
                                              │   escalation; flag ticket│
                                              └──────────────┬───────────┘
                                                             ▼
                              ┌──────────────────────────────────────────────┐
                              │ SQLite: sessions · messages · tickets ·      │
                              │ knowledge_gaps · guardrail_violations        │
                              └──────────────────────────────────────────────┘
```

## Three things that make this different from a generic support bot

**1. Level 1 sends no email.** The bottom level is a resolution path, not an escalation. Most implementations of a tiered system make every level route somewhere; here the bot must actually solve the problem, and only escalates if it cannot. That changes what "containment rate" means — see the metrics document.

**2. The safety floor is independent of the model.** `level = max(model_assessed, safety_floor)`. The floor can only raise. It exists because at Level 3 a miss is an unreported child injury, and a judgement component that is right 97% of the time is not sufficient for that.

**3. Send-then-confirm.** The customer is told an escalation happened only after the email actually sent. This inverts the natural ordering — most systems reply first and send in the background — and it exists because system-guardrails §3 forbids the alternative. A cheerful "escalated!" over a failed send is the worst outcome available: the customer stops chasing and nobody was told.

## Pre-filter ordering

Order matters and is not arbitrary:

1. **Rate limit** — cheapest check, and stops flooding before anything expensive runs.
2. **PII redaction** — before any write, so nothing sensitive is ever persisted even briefly.
3. **Injection check** — before the message reaches any prompt.
4. **Scope check** — declines homework, stories and chit-chat without spending a retrieval call.
5. **Safety floor scan** — last, because it must see the redacted text but must run before the router can choose a non-escalation path.

The safety scan consults the model's event-versus-question classification before firing, because a keyword net alone cannot separate "what happens if this catches fire" from "the toy caught fire".

## What is indexed

Knowledge base sections **1 to 7 only**. Sections 8 (escalation triggers) and 9 (conversational workflow) are behaviour specifications — both say so in their own text. They load into the system prompt and the router, never into the vector store. Indexing them lets a customer retrieve the internal escalation logic, which system-guardrails §4 forbids.

## Menu as application logic

The greeting menu is hardcoded and never generated. Menu numbering is deliberately decoupled from knowledge base numbering via `config/menu_map.json` — menu item 4.2 maps to KB §5.2 — so the customer-facing structure and the corpus structure can evolve independently.

Menu state lives on the session and is cleared on any free-text answer and on any escalation. Stale menu state is what causes a later bare "3" to be misread as a menu selection.

## What is deliberately not built

No live order lookup, no account system, no authentication, no payment handling, no multi-tenancy, no reply-ingestion loop, no voice transcription. Each is recorded in `docs/scope-and-backlog.md` with the reason and the level it escalates to instead.
