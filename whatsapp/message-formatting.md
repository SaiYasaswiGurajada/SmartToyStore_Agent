# WhatsApp Message Formatting

The web version could render tables and headings. WhatsApp cannot. Answers must be rewritten for the channel, not just piped into it.

## Constraints

| Constraint | Value | Consequence |
|---|---|---|
| Max body length | 1600 characters via Twilio | Split longer answers |
| Markdown | Not supported | No `#`, no `|` tables, no `-` bullets rendered as bullets |
| Formatting | `*bold*` `_italic_` `~strike~` and triple-backtick mono | Single asterisks, not double |
| Links | Auto-linked, no control over preview | Keep URLs to the end of a message |
| Typing indicator | Not available through the Twilio sandbox | The brief's requirement is met by the web UI, not here |

## Rules for the answer skill

Add these to the channel-specific prompt when `CHANNEL=whatsapp`:

- Target **under 700 characters**. A retailer reads this on a phone between customers.
- Never emit a markdown table. Convert a table row to a sentence: "Delivery to Pune takes 5 to 7 business days."
- At most three list items, each on its own line prefixed with `•` (a literal bullet character, since `-` renders as a hyphen).
- Bold only the figure that answers the question: `Delivery to Pune takes *5 to 7 business days*.`
- Never split one answer across two messages unless it exceeds 1500 characters. Two notifications for one answer is worse than a slightly long message.
- Troubleshooting sequences are the exception: numbered steps, one per line, up to six.

## Splitting

If an answer exceeds 1500 characters, split on paragraph boundaries and send sequentially with a short delay so ordering holds. Never split mid-sentence and never split a numbered sequence across messages.

## Escalation notices

The web UI showed an inline system banner. On WhatsApp the notice is just another message, so wording carries the whole weight.

**Levels 1 to 3:**

> I don't have that documented, so I've passed it to our team. Someone will follow up with you directly.

Never state the level. Never name the recipient. Never promise a response time beyond the published SLA.

**Level 4** — calm, short, actionable. Do not use urgency formatting, capital letters or alarming punctuation at a retailer who has just reported an injury or a fire:

> Thank you for reporting this. Please stop selling that batch and set the stock aside. I've escalated this as a priority and our team will contact you directly.

Three sentences. No diagnosis, no fix, no questions.

## Voice notes

Indian B2B WhatsApp runs heavily on voice notes. `MediaContentType` of `audio/ogg` will appear in real use.

For this build, reply asking for text:

> I can't listen to voice notes yet — could you type the key details?

Transcription is in the backlog. Handling it badly (silently ignoring the audio) looks like the bot is broken, which is worse than declining clearly.
