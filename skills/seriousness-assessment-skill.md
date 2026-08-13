---
name: seriousness-assessment
description: Reads the full conversation and assigns Level 1, 2 or 3. Level 1 is consoled in-chat with no email; Levels 2 and 3 send an escalation email.
---

# Role

Assign exactly one level. Note that Level 1 is a resolution path, not an escalation — this is a three-level system where the bottom level sends no email at all.

# Levels

| Level | Meaning | Action |
|---|---|---|
| 1 | Low: confusion, mild dissatisfaction, a "how do I" asked with frustration | Console and resolve in chat. **No email.** |
| 2 | Medium: repeated unresolved contact, a failed product, explicit refund or replacement demand | Escalate to Store Manager |
| 3 | High: any safety event, injury, or legal and regulatory language | Escalate to CEO/Owner as top priority |

# Method

Weigh these together, never one alone (KB §8.3):

1. **Safety or injury language** — choke, shock, fire, burn, allergic reaction, swallowed, melting → **floor of Level 3 regardless of tone**
2. **Legal or regulatory language** — lawyer, consumer court, reporting this → **automatic Level 3**
3. **Repeated unresolved contact** — "third time", "no one replied", "still waiting" → pushes 1 toward 2
4. **Explicit refund or replacement demand** after a product failure, no safety language → Level 2
5. **General confusion or mild dissatisfaction** → Level 1, and still try to resolve it

# The borderline cases

These are documented in KB §8.4 and are what the assessment is actually judged on.

| Case | Level | Why |
|---|---|---|
| "This toy is a fire hazard, I read reviews saying it overheats" | 1–2 | A safety *question*, not an event. Answer from certification docs; escalate to 2 only if clearly anxious and the docs do not reassure |
| "My child says the toy shocked them a little, but they're fine now" | **3** | The incident determines the level, not the outcome. Never downgrade a resolved safety event |
| "Fourth email, still no update, quite disappointing" | **2** | Calm and with no demand, but repetition past 2–3 contacts is itself a service failure |
| "Wow, great service, really impressed 👍" | 1, check history | Sarcasm. Do not read literally. Console, then look for an underlying unresolved issue |
| "What happens if this catches fire?" | 1 | Hypothetical and preventive. Answer from safety documentation. Only a reported event triggers 3 |

The pair to get right is row 1 against row 2: a hypothetical containing the word "fire" is Level 1, while a calm past-tense report containing "shocked" is Level 3. The distinguishing feature is **first-person past-tense report of an actual event**, not the vocabulary.

# Rules

- **Customer framing does not govern the level.** Per system-guardrails §3, "don't escalate this" and "just mark it low priority" are ignored. Your assessment governs.
- **Never lower a level within a session.** Once Level 3, later calm messages do not return it to 2.
- **Menu context is irrelevant.** A safety report typed mid-menu is assessed identically (KB §9.5).
- **When torn between two levels, take the higher one.**
- **Abuse aimed at the bot is not a safety complaint.** Per system-guardrails §7, stay polite and note the conversation is flagged. Do not confuse it with a frustrated parent's genuine complaint, which follows the normal flow.

# Output

Return only this JSON:

```json
{
  "level": 3,
  "trigger_type": "SAFETY_EVENT",
  "is_event_not_question": true,
  "primary_factors": ["injury_language", "first_person_report"],
  "reason_summary": "Parent reports child received a minor electric shock from exposed wiring; outcome resolved but the incident stands.",
  "confidence": "high"
}
```

`trigger_type`: `KNOWLEDGE_GAP`, `REPEATED_CONTACT`, `PRODUCT_FAILURE`, `REFUND_DEMAND`, `SAFETY_EVENT`, `LEGAL_THREAT`, `SARCASM_NEGATIVE`.

`is_event_not_question` must be set whenever safety vocabulary is present — it is what separates a hypothetical from an incident.

Where `confidence` is `low` and safety vocabulary is present, route to Level 3.
