---
name: menu-navigation
description: Greeting-triggered menu, submenu mapping to knowledge base subsections, and the rules that keep the menu a shortcut rather than a gate.
---

# Role

Implements KB §9. The menu is application logic, not retrieved content — it is hardcoded and never generated.

# Entry

A greeting-only message ("Hi", "Hello", "Hey", "Namaste") triggers the fixed menu verbatim:

```
Hello! 👋 I'm here to help with anything about your smart toy.
Choose a topic to get started, or just type your question anytime:
1. Connectivity & Setup
2. Features & How It Works
3. Battery & Maintenance
4. Pricing & Discounts
5. Orders, Delivery, Warranty & Safety
```

**Greeting-only.** "Hi, my toy won't pair" is not a greeting — it is a question with a greeting attached. Answer it directly and never show the menu (KB §9.3).

# Submenu

A top-level number shows its subpoints, mapped to knowledge base subsections via `config/menu_map.json`. Selecting a subpoint retrieves that exact chunk and answers.

Menu numbering is **not** knowledge base numbering. Menu item 4.2 maps to KB §5.2. Keep the mapping in the config file so the two can drift independently without breaking.

# The three rules that matter

**1. Free text is always open.** The menu is a shortcut, not a gate. At any point — before, during, after — a typed question is answered directly. Never reply "please choose an option from the menu."

**2. Answer-first is the default.** Every message after entry attempts a knowledge base answer first. Escalation is the exception path, triggered only by the seriousness assessment. A question outside the five menu topics is still answered if the corpus covers it (KB §9.4).

**3. Escalation ignores menu state entirely.** Per KB §9.5 and system-guardrails §3, a customer mid-menu who reports a safety incident hits the Level 3 floor immediately. The menu is abandoned mid-flow, with no "let me just finish showing you the options." This is the trace in KB §9.6 and it is worth demonstrating live.

# Invalid input

- A number outside range → reshow the current menu once, briefly, without scolding.
- Free text while a menu is displayed → treat as a question, drop the menu.
- Two consecutive invalid inputs → drop the menu and ask what they need in plain words. A child mistyping should not get stuck in a loop.

# Menu state

Store the current menu position on the session so a bare "2" is interpretable. Clear it whenever a free-text question is answered, and clear it immediately on any escalation. Stale menu state causes a later "3" to be read as a menu choice rather than a quantity.
