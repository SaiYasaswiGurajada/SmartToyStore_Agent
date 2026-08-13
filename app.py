"""
Smart Toy Store Support Assistant — FastAPI entry point.

Startup:
  1. Load .env; validate required variables → styled error if missing.
  2. Init SQLite database.
  3. Build vector index from default KB files.

Routes:
  GET  /                  → chat UI
  POST /chat              → web chat pipeline
  POST /upload            → file ingestion
  GET  /admin             → admin panel
  GET  /api/admin/*       → admin JSON API
  POST /webhook/whatsapp  → Twilio WhatsApp webhook
"""

from __future__ import annotations
import os
import sys
import uuid
from pathlib import Path

# Load .env BEFORE importing config
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# ---- Validate required environment variables ----
_REQUIRED = {
    "LLM_API_KEY": "Your OpenAI API key (from platform.openai.com/api-keys)",
}
_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    print("\n" + "="*60)
    print("  Smart Toy Store — STARTUP ERROR")
    print("="*60)
    for var in _missing:
        print(f"  ✗  {var} is not set")
        print(f"     → {_REQUIRED[var]}")
    print("\n  Copy .env.example to .env and fill in the missing values.")
    print("="*60 + "\n")
    sys.exit(1)

# ---- Now safe to import everything ----
from fastapi import (
    FastAPI, Request, BackgroundTasks, UploadFile, File,
    HTTPException, Header
)
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import tempfile

from pipeline.db import (
    init_db, get_tickets_for_admin, get_top_knowledge_gaps,
    get_placeholder_gaps, get_violations_by_type, get_metrics,
)
from pipeline.indexer import load_default_kb, parse_file
from pipeline.retriever import build_index, add_chunks
from pipeline.responder import process_turn
from pipeline.session import new_session_id
from pipeline.whatsapp import (
    validate_signature, parse_payload, process_whatsapp_message, EMPTY_TWIML
)
from config.config import (
    CHANNEL, PUBLIC_WEBHOOK_URL, MAX_UPLOAD_MB, ALLOWED_UPLOAD_EXTENSIONS,
    ROOT,
)

# ---- App ----
app = FastAPI(
    title="Smart Toy Store Support Assistant",
    description="AI-powered 24/7 support agent for SmartToyStore",
    version="1.0.0",
)

STATIC_DIR = ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---- Startup ----
@app.on_event("startup")
async def startup_event():
    print("[app] Initialising database …")
    init_db()
    print("[app] Loading knowledge base …")
    chunks = load_default_kb()
    print(f"[app] {len(chunks)} chunks loaded from default KB.")
    build_index(chunks)
    print("[app] Ready.")


# ============================================================
# Web UI Routes
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    index_html = STATIC_DIR / "index.html"
    return HTMLResponse(index_html.read_text(encoding="utf-8"))


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    admin_html = STATIC_DIR / "admin.html"
    return HTMLResponse(admin_html.read_text(encoding="utf-8"))


# ============================================================
# Chat API
# ============================================================

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    session_id = body.get("session_id") or new_session_id()

    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    result = process_turn(
        raw_message=message,
        session_id=session_id,
        channel="web",
    )

    return JSONResponse({
        "reply": result["text"],
        "action": result["action"],
        "options": result.get("options"),
        "ticket_id": result.get("ticket_id"),
        "session_id": result["session_id"],
    })


# ============================================================
# File Upload
# ============================================================

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_UPLOAD_EXTENSIONS}",
        )

    size_bytes = 0
    content = await file.read()
    size_bytes = len(content)

    if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_MB}MB limit.",
        )

    # Save to temp, parse, index
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        chunks = parse_file(tmp_path)
        # Give chunks the original filename as source
        for chunk in chunks:
            chunk.source = file.filename
        add_chunks(chunks)
    finally:
        tmp_path.unlink(missing_ok=True)

    flagged = sum(1 for c in chunks if c.placeholder_flagged)
    return JSONResponse({
        "filename": file.filename,
        "chunks_ingested": len(chunks),
        "placeholder_flagged": flagged,
        "message": (
            f"✓ Ingested {len(chunks)} chunks from '{file.filename}'."
            + (f" ({flagged} chunks flagged for unfilled placeholders)" if flagged else "")
        ),
    })


# ============================================================
# WhatsApp Webhook
# ============================================================

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: str = Header(default=""),
):
    form_data = dict(await request.form())
    webhook_url = PUBLIC_WEBHOOK_URL or str(request.url)

    # Signature validation — reject with 403 if invalid
    if not validate_signature(webhook_url, form_data, x_twilio_signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Parse payload
    payload = parse_payload(form_data)

    # Enqueue processing in background — return TwiML immediately
    background_tasks.add_task(process_whatsapp_message, payload)

    return HTMLResponse(content=EMPTY_TWIML, media_type="application/xml")


# ============================================================
# Admin API
# ============================================================

@app.get("/api/admin/tickets")
async def admin_tickets():
    rows = get_tickets_for_admin()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/admin/gaps")
async def admin_gaps():
    top = get_top_knowledge_gaps()
    placeholder = get_placeholder_gaps()
    return JSONResponse({
        "top_clusters": [dict(r) for r in top],
        "placeholder_blocked": [dict(r) for r in placeholder],
    })


@app.get("/api/admin/violations")
async def admin_violations():
    rows = get_violations_by_type()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/admin/metrics")
async def admin_metrics():
    return JSONResponse(get_metrics())


# ============================================================
# Health check
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok", "channel": CHANNEL}
