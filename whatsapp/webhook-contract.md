# WhatsApp Webhook Contract

## Inbound: `POST /webhook/whatsapp`

Twilio sends `application/x-www-form-urlencoded`, not JSON.

| Field | Example | Use |
|---|---|---|
| `MessageSid` | `SM1a2b3c...` | **Idempotency key.** Store it; reject duplicates |
| `From` | `whatsapp:+919876543210` | Strip the `whatsapp:` prefix → session key |
| `To` | `whatsapp:+14155238886` | Your sandbox number |
| `Body` | `My order is late` | The retailer's message |
| `ProfileName` | `Sharma Toys` | WhatsApp display name → `chat_sessions.shop_name` |
| `WaId` | `919876543210` | Stable retailer identifier |
| `NumMedia` | `2` | Count of attachments |
| `MediaUrl0..N` | `https://api.twilio.com/...` | Requires Basic auth with your SID and token to fetch |
| `MediaContentType0..N` | `image/jpeg` | Filter to images for damage claims |

## The response rule

**Return an empty TwiML response immediately. Never generate inside the request.**

```
<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>
```

Generation takes several seconds. A slow webhook gets re-delivered, and a re-delivery means a duplicate escalation email — which defeats the deduplication in the escalation engine. Return within ~500ms, do the work in a background task, send the reply as a separate outbound REST call.

```python
@app.post("/webhook/whatsapp")
async def inbound(request: Request, tasks: BackgroundTasks):
    form = await request.form()
    if not valid_signature(request, form):
        return Response(status_code=403)
    if already_processed(form["MessageSid"]):
        return Response(content=EMPTY_TWIML, media_type="application/xml")
    mark_processed(form["MessageSid"])
    tasks.add_task(handle_message, dict(form))
    return Response(content=EMPTY_TWIML, media_type="application/xml")
```

## Signature validation

Twilio signs every request with `X-Twilio-Signature`. Validate it — an unvalidated webhook is an open endpoint anyone can POST fabricated retailer messages to, including fake Level 4 escalations.

```python
from twilio.request_validator import RequestValidator

validator = RequestValidator(TWILIO_AUTH_TOKEN)
ok = validator.validate(public_url, dict(form), request.headers["X-Twilio-Signature"])
```

`public_url` must be the exact HTTPS URL Twilio called, including the ngrok domain. Behind a tunnel your app sees `http://localhost:8000`, so reconstruct from the `X-Forwarded-Proto` and `Host` headers or set the public URL explicitly in config. Getting this wrong produces a `403` on every message and is the single most common setup failure.

## Outbound

```python
client.messages.create(
    from_=TWILIO_WHATSAPP_FROM,   # "whatsapp:+14155238886"
    to=f"whatsapp:+{wa_id}",
    body=text,
)
```

Log the returned SID in `outbound_messages` so a missing reply can be traced to a send failure rather than a generation failure.

## Session mapping

| Web version | WhatsApp version |
|---|---|
| Generated UUID per browser session | `wa_id` (the phone number) |
| Session ends when the tab closes | Session is a rolling window — define an idle timeout |
| Shop name unknown | `ProfileName` from the payload |

**Session boundary rule.** A phone number is permanent, a conversation is not. Close the session and start a new one after **12 hours of inactivity**, so a question next week does not inherit last week's escalation state.

The exception is a `CRITICAL` session: a Level 4 does not expire on a timer. Keep it terminal until an operator closes it manually, otherwise a retailer who reported an injury gets automated answers again tomorrow morning.

## Media handling

Damage claims require photographs, and WhatsApp is the natural way to send them — this is a genuine capability gain over the web version, not a port.

When `NumMedia > 0`:

1. Fetch each `MediaUrl` using Basic auth (SID and auth token). Twilio media URLs are not public.
2. Store locally under the session, record the path in `inbound_media`.
3. Attach to the escalation email if one fires.
4. Media alone with no text is a knowledge gap by definition — ask what the photo shows rather than guessing.

Do not run the images through a vision model unless you scope that deliberately. Storing and forwarding them is enough, and it is what a damage claim actually needs.

## The 24-hour service window

Meta opens a free-form window when the retailer messages you. Inside it, any reply is free and needs no template. Outside it, a business-initiated message requires a pre-approved template.

Your assistant only ever replies, so it is always inside the window. The constraint bites on the **human follow-up**: an agent replying two days later cannot send free-form text.

Handle it as:

- Store `last_inbound_at` on the session.
- If a human follow-up is attempted more than 24 hours later, do not silently fail — flag it in the ticket and fall back to a pre-approved utility template, or route the follow-up to email.
- Record this in the decision log. Designing around a platform constraint you did not choose is exactly the kind of reasoning that distinguishes a product decision from an implementation detail.
