# Placeholders — Fill Before Indexing

**This is the blocking item for the whole build.** Guardrail 1.1 says the bot must never answer outside retrieved context. Your knowledge base currently contains bracketed placeholders in the sections customers ask about most. The interaction between those two facts is predictable: every pricing, delivery and warranty question will escalate as a knowledge gap.

That is technically correct behaviour and a bad demo. Containment rate collapses and the reviewer sees a bot that escalates almost everything.

## Must fill — high query volume

| Section | Placeholder | Why it matters |
|---|---|---|
| 5.1 | `[Insert current price list or link]` | Highest-frequency question in retail support |
| 5.2 | `[Insert current active offers]` | Second highest, especially seasonal |
| 5.3 | `[X units]` for bulk threshold | Schools and daycare enquiries |
| 5.5 | Price matching policy | Currently unanswerable either way |
| 6.1 | `[X–Y business days]`, `[region]` | Every order query |
| 6.2 | `[X-month/year]` warranty term | Every defect query |
| 6.3 | `[X days]` return window | Every return query |
| 6.4 | International shipping policy | — |

## Must fill — safety-critical

These carry more weight than the commercial ones. Guardrail 1.3 forbids claiming a certification the documents do not state, and a false safety claim from a toy retailer is a liability issue.

| Section | Placeholder | Note |
|---|---|---|
| 7.1 | `[ASTM F963 / EN71 / BIS / CE]` | State only certifications the products genuinely hold. If unsure for the fictional business, pick one standard and be consistent |
| 7.3 | Additional material details | Keep to what is stated; do not expand |

## Optional

5.4 loyalty programme and seasonal sales — safe to leave out. Sections you deliberately omit become clean Level 1 knowledge gaps, which you want some of.

## Recommended values for a demo

Pick values and keep them consistent across the KB, FAQ and test suite. Suggested for an India-based store:

- Delivery: 3–5 business days metro, 5–8 elsewhere in India
- Warranty: 12 months manufacturer warranty
- Returns: 15 days from delivery for defective items
- Bulk threshold: 10 units
- Price matching: not offered
- International shipping: not offered
- Certification: BIS under IS 9873, plus CE for imported models

## Deliberate gaps to keep

Do **not** fill these. They are your designed escalation paths and the reason Level 1 and Level 2 have any traffic:

- Live order status for a specific order number (6.5 tells the customer where to self-serve; the bot has no lookup)
- Custom bulk quotes (5.3 already routes these to sales)
- Goodwill refunds and exceptions outside stated policy
- Whether a specific batch has a defect

Record these in the decision log as intentional scope, not oversights.
