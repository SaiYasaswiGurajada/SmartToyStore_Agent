---
trigger: always_on
name: safety-floor-rules
description: Deterministic Level 3 floor for safety and legal language. Runs independently of the seriousness model and can only raise a level, never lower it.
---

# Level 3 Safety Floor

Operationalises system-guardrails §3 and knowledge base §8.3.

## Why a separate layer

The seriousness model is a judgement component and judgement fails occasionally. At Levels 1 and 2 a misroute costs someone minutes. At Level 3 a miss is an unreported child injury. This layer therefore runs **independently of the model** and can only raise.

```
final_level = max(model_assessed_level, safety_floor_level)
```

The floor never reduces a level the model assigned. Model says 3, floor says nothing → the level is 3.

## Floor triggers

**Injury and safety events** — floor of Level 3 regardless of tone, per KB §8.3:

choke, choked, choking, swallow, swallowed, shock, shocked, electrocuted, burn, burnt, burned, fire, caught fire, smoke, smoking, melting, melted, overheat, overheating, sparking, allergic, allergic reaction, rash, hospital, emergency, bleeding, injured, injury, hurt, cut

**Legal and regulatory** — floor of Level 3, per KB §8.3:

lawyer, advocate, legal notice, sue, suing, court, consumer court, consumer forum, consumer safety authority, reporting this, complaint to authorities, FIR

## The three rules that matter most

**1. A calm report is still Level 3.** "My daughter had a small reaction, she's fine now, just letting you know" contains no anger and no demand. It is Level 3. Tone is not a factor at this tier.

**2. Outcome does not downgrade the incident.** KB §8.4 is explicit: "my child says the toy shocked them a little, but they're fine now" routes to Level 3. The event determines the level, not how it ended.

**3. Menu state never delays the floor.** Per system-guardrails §3 and KB §9.5, a safety report typed mid-menu interrupts the flow immediately. There is no "let me finish showing you options first."

## What the floor must NOT catch

The floor is a keyword net, and keyword nets over-fire. Two documented cases from KB §8.4 must stay below Level 3:

- **Hypothetical questions.** "What happens if this catches fire?" is a safety *question*, not a safety *event*. Level 1, answered from certification documentation.
- **Second-hand concern with no personal incident.** "I read reviews saying it overheats" is Level 1–2, escalating to 2 only if the customer is clearly anxious and the documentation does not reassure them.

Distinguish by **who and when**: a first-person past-tense report of something that happened is an event. A conditional, future-tense or third-party statement is a question. The model makes this call; the keyword list alone cannot, so the floor must consult the model's event/question classification before firing on a hypothetical.

This is the one place the floor is not purely mechanical, and it is worth saying so in the write-up rather than pretending the keyword list solves it.

## Behaviour when the floor fires

Per KB §8.5 and §9.6:

1. **No troubleshooting.** Do not retrieve setup steps, do not diagnose, do not ask the customer to test the toy again.
2. **Brief acknowledgement.** No over-apologising — a parent whose child was hurt does not want three paragraphs of regret.
3. **One immediate-safety instruction if applicable.** "Please stop using the toy and unplug it now."
4. **Confirm escalation to the owner as top priority** — but only after the email has actually sent (system-guardrails §3, no silent failures).
5. **Mark the session so every later message stays Level 3.**

## Accepted cost

False positives reach the CEO. A false Level 3 costs the owner a few minutes of reading. A missed one is a child injury nobody acted on. The asymmetry is deliberate and belongs in the decision log.
