---
trigger: always_on
name: grounding-and-confidence
description: Retrieval mechanics, the two-stage confidence check, and the placeholder trap. Implements system-guardrails §1 as measurable behaviour.
---

# Grounding and Confidence

## Two-stage confidence

System-guardrails §1.2 requires escalation rather than hedging below the threshold. A single similarity score is a weak basis for that decision, so confidence is assessed twice and both must pass.

**Stage 1 — retrieval score.** Cosine similarity over the indexed chunks, top K = 4. Below **0.75**, stop. No generation is attempted.

**Stage 2 — evidence check.** A structured call returning exactly one of:

- `SUPPORTED` → answer directly
- `PARTIAL` → the topic is covered but a parameter is missing; ask one clarifying question
- `UNSUPPORTED` → escalate as a knowledge gap

Stage 2 exists because retrieval scores highly on topically adjacent chunks that contain no answer. "Do you offer school discounts?" retrieves §5.3 at a strong score, and §5.3 says only that such requests route to sales.

## What is indexed

**Index sections 1 to 7 only.**

Knowledge base §8 (escalation triggers) and §9 (conversational workflow) are behaviour specifications, not retrievable content — both sections say so explicitly. Indexing them causes two failures: the bot retrieves and recites its own escalation logic to a customer, which system-guardrails §4 forbids; and a customer asking "what happens if I complain" gets an answer describing the internal hierarchy.

Load §8 and §9 into the system prompt and the router. Never into the vector store.

## The placeholder trap

Unfilled bracketed placeholders such as `[X days]` and `[Insert current price list]` will retrieve at a high similarity score and read as answer-shaped content. The bot may then emit a placeholder as though it were a policy.

Two protections, both required:

1. **Fill them before indexing.** See `kb/PLACEHOLDERS_TO_FILL.md`.
2. **Reject at index time as a backstop.** Any chunk matching `\[[^\]]{3,}\]` is flagged; if such a chunk is the top result, force `UNSUPPORTED` regardless of score. Emitting `[X days]` to a customer is worse than escalating.

## Retrieval rules

- **Chunk at subsection level** (1.1, 2.3, 5.2) exactly as the KB's own implementation notes specify. Each is written self-contained. Never split mid-subsection.
- Keep the subsection heading in the chunk text — headings carry most of the retrieval signal for short factual sections.
- Retrieve K = 4. Some answers span two subsections (pairing failure spans 2.2 and 2.4).
- Carry the subsection number of every chunk used into the log, so any answer traces to its source.

## Never claim what is not stated

System-guardrails §1.3 singles out certifications and safety ratings. Enforce it specifically: if the answer would name a standard, a certification body or a safety rating, it must appear verbatim in a retrieved chunk. No inference from "compliant with applicable regulations" to a named standard. A false safety claim from a toy retailer is a liability issue, not an inaccuracy.

## Logging

Every message logs the query, top score, evidence verdict, subsection identifiers used, whether a placeholder chunk was hit, and the resulting action. Knowledge-gap escalations also write to `knowledge_gaps`, which drives the content gap report.
