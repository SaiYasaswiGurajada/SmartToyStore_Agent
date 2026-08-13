# Smart Toy Store Support Assistant — Agent Bundle

A 24/7 AI support agent for a B2C smart toy retailer. Answers strictly from the knowledge base, consoles and resolves low-level frustration without escalating, and routes safety, legal and repeated-failure cases to a person by email.

Everything the agent needs **except the code**. Point Antigravity at `Final Prompt.txt`.

## Read these first

1. **`kb/PLACEHOLDERS_TO_FILL.md`** — blocking item. The knowledge base contains bracketed placeholders in pricing, delivery, warranty and certification. Combined with the grounding guardrail, every one of those questions currently escalates.
2. **`Final Prompt.txt`** — the build prompt.
3. **`whatsapp/SETUP_AND_TEST.md`** — 45-minute channel runbook.

## Layout

```
SmartToyStore_Agent/
├── Final Prompt.txt              build prompt for the IDE
├── README.md
├── .env.example                  credential template; copy to .env
├── .gitignore
│
├── kb/
│   ├── smart_toy_store_knowledge_base.md   your authored corpus, unchanged
│   ├── PLACEHOLDERS_TO_FILL.md             what must be filled, and what to leave out
│   └── FAQ.txt                             quick FAQ, exercises the .txt parser
│
├── guardrails/                   always-on, injected every turn
│   ├── system-guardrails.md                your authored spec, unchanged
│   ├── grounding-and-confidence.md         thresholds, index scope, placeholder trap
│   ├── safety-floor-rules.md               Level 3 floor, and what it must NOT catch
│   └── child-safety-rules.md               §2 turned into enforceable behaviour
│
├── skills/
│   ├── rag-answer-skill.md
│   ├── console-skill.md                    Level 1 — the level that sends no email
│   ├── seriousness-assessment-skill.md     3 levels, with the §8.4 borderline cases
│   ├── escalation-email-skill.md           send-then-confirm
│   └── menu-navigation-skill.md            §9 workflow
│
├── docs/
│   ├── architecture.md
│   ├── decision-log.md                     19 decisions with trade-offs
│   ├── metrics-and-evaluation.md
│   ├── risk-register.md                    16 risks
│   └── scope-and-backlog.md
│
├── config/
│   ├── config.py
│   ├── schema.sql                          five tables
│   ├── schema_whatsapp_migration.sql
│   ├── escalation_hierarchy.json           3 levels; Level 1 sends no email
│   └── menu_map.json                       menu numbering ≠ KB numbering
│
├── whatsapp/
│   ├── SETUP_AND_TEST.md
│   ├── webhook-contract.md
│   └── message-formatting.md
│
└── tests/
    └── golden_test_suite.csv               60 labelled cases
```

## Setup

```bash
cp .env.example .env      # fill in, never commit
pip install fastapi uvicorn python-dotenv openai pymupdf python-docx numpy twilio
```

Only two escalation addresses are needed — Level 1 sends no email.

## The three structural rules

Everything else follows from these. If the build gets them wrong, nothing else matters.

**Level 1 sends no email.** It consoles *and resolves*. Most tiered systems route every level somewhere; here the bottom level must actually help. That makes Level 1 quality load-bearing — a sympathetic reply that solves nothing looks like a working system while helping nobody.

**The safety floor sits above the model.** `level = max(model, floor)`, raise-only. But it consults the model's event-versus-question classification before firing, because "what happens if this catches fire" and "the toy caught fire" share vocabulary and sit at opposite levels.

**Send, verify, then confirm.** The customer hears about an escalation only after the email actually sent. `customer_informed = 1 AND send_status != 'SENT'` must always return zero rows.

## The demo

Seven cases carry the argument — listed in `docs/metrics-and-evaluation.md`. The one to show live is **TC-50**: navigate the menu, select 4, select 4.2, then type a fire report. The menu is abandoned mid-flow and the escalation fires immediately. That is the trace from your own KB §9.6, and it demonstrates the menu, the floor, and the override in one interaction.

## Before submitting

- Work through `PLACEHOLDERS_TO_FILL.md` — without it containment collapses
- Replace the placeholder addresses in `escalation_hierarchy.json`
- Confirm `.env` is not in the repository (`.gitignore` does not apply to `zip` — use `-x "*.env"`)
- Fill the tuning table in `decision-log.md` and the result tables in `metrics-and-evaluation.md`
