"""
app.py — Sonora HVAC Backend
Main Flask application — "The Voice of Your Business"

Endpoints:
  POST /api/chat              — Text chat with Sonora
  POST /api/voice             — Voice call (audio in → Sonora response + TTS audio)
  GET  /api/leads             — All leads
  GET  /api/leads/<id>        — Lead detail
  PUT  /api/leads/<id>        — Update lead
  GET  /api/appointments      — All appointments
  POST /api/appointments      — Book appointment
  PUT  /api/appointments/<id> — Update appointment
  GET  /api/dashboard         — Business stats
  POST /api/webhook/ghl       — GoHighLevel webhook receiver
  POST /api/tts               — Text → TTS audio (OpenAI nova)
  POST /api/sms/send          — Send SMS via Twilio
  GET  /api/reviews           — Review request queue
  POST /api/reactivate        — Trigger seasonal reactivation campaign
  GET  /api/health            — Health check
"""

import io
import os
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Optional

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

from config import config
from sonora.crm import (
    init_db, LeadCRM, AppointmentCRM, ConversationCRM,
    FollowUpCRM, ReviewCRM, BusinessCRM
)
from sonora.agent import SonoraAgent
from sonora.voice import (
    synthesize_speech, synthesize_speech_b64, transcribe_audio,
    voice_health_check
)
from sonora.follow_up import (
    start_followup_scheduler, schedule_appointment_reminders,
    schedule_post_job_review, schedule_seasonal_reactivation,
    process_due_follow_ups, generate_message
)
from sonora.ghl import (
    process_ghl_webhook, verify_ghl_webhook_signature,
    sync_lead_to_ghl, sync_appointment_to_ghl, ghl_status
)

# ─────────────────────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# CORS — allow all origins (restrict in production as needed)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
origins = allowed_origins.split(",") if allowed_origins != "*" else "*"
CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)

# Initialize database on startup
init_db()

# Instantiate Sonora agent (singleton — handles session memory internally)
_agent = SonoraAgent(business_id=1)

# SMS client (lazy, Twilio)
_sms_client = None


def get_sms_client():
    """Lazy-init Twilio client. Returns None if not configured."""
    global _sms_client
    if _sms_client is not None:
        return _sms_client
    if not config.has_twilio():
        return None
    try:
        from twilio.rest import Client
        _sms_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        logger.info("Twilio SMS client initialized")
        return _sms_client
    except ImportError:
        logger.warning("twilio package not installed — SMS disabled")
        return None
    except Exception as e:
        logger.error("Twilio init error: %s", e)
        return None


def send_sms_twilio(phone: str, message: str) -> bool:
    """Send an SMS via Twilio. Returns True on success."""
    client = get_sms_client()
    if not client:
        logger.info("[SMS DRY RUN] To %s: %s", phone, message[:80])
        return True  # Graceful no-op
    try:
        msg = client.messages.create(
            body=message,
            from_=config.TWILIO_FROM_NUMBER,
            to=phone,
        )
        logger.info("SMS sent to %s — SID: %s", phone, msg.sid)
        return True
    except Exception as e:
        logger.error("Twilio SMS error to %s: %s", phone, e)
        return False


# Start the follow-up scheduler
start_followup_scheduler(sms_sender=send_sms_twilio)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ok(data=None, **kwargs) -> Response:
    payload = {"success": True, **(data or {}), **kwargs}
    return jsonify(payload)


def err(message: str, status: int = 400, **kwargs) -> tuple:
    payload = {"success": False, "error": message, **kwargs}
    return jsonify(payload), status


def require_json(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json and request.method in ("POST", "PUT", "PATCH"):
            return err("Content-Type must be application/json", 415)
        return f(*args, **kwargs)
    return decorated


def safe_int(value, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return ok(
        status="healthy",
        service="Sonora HVAC Backend",
        tagline="The Voice of Your Business",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        features={
            "openai": config.has_openai(),
            "twilio_sms": config.has_twilio(),
            "ghl_integration": config.has_ghl(),
            **voice_health_check(),
        },
        ghl=ghl_status(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chat — POST /api/chat
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
@require_json
def chat():
    """
    Text chat with Sonora.

    Request body:
        message    (str, required)
        session_id (str, required) — unique caller/session identifier
        business_id (int, optional, default 1)

    Response:
        response   — Sonora's text reply
        audio_url  — null (use /api/tts to get audio)
        lead_data  — extracted lead qualification data
    """
    body = request.get_json()
    message = (body.get("message") or "").strip()
    session_id = (body.get("session_id") or "").strip()
    business_id = safe_int(body.get("business_id"), 1)

    if not message:
        return err("message is required")
    if not session_id:
        return err("session_id is required")

    try:
        _agent.set_session_business(session_id, business_id)
        response_text, lead_data = _agent.chat(session_id, message, business_id=business_id)

        # Attempt TTS if configured (small payload — b64)
        audio_b64 = None
        if config.has_openai() and body.get("include_audio"):
            audio_b64 = synthesize_speech_b64(response_text)

        return ok(
            response=response_text,
            audio_b64=audio_b64,
            audio_url=None,  # Clients can use POST /api/tts with the response text
            lead_data=lead_data,
            session_id=session_id,
        )

    except Exception as e:
        logger.error("Chat error: %s\n%s", e, traceback.format_exc())
        return err("Internal error processing message", 500)


# ─────────────────────────────────────────────────────────────────────────────
# Voice — POST /api/voice
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/voice")
def voice():
    """
    Full voice pipeline: audio in → Sonora text reply → TTS audio out.

    Accepts multipart/form-data:
        audio      — audio file (webm, mp3, wav, etc.)
        session_id — unique session identifier
        business_id — (optional, default 1)

    OR application/json with base64-encoded audio:
        audio_b64  — base64 audio string
        audio_format — file format hint (default "webm")
        session_id
        business_id

    Response:
        transcript   — what Sonora heard
        response     — Sonora's text reply
        audio_b64    — TTS audio as base64 data URI
        lead_data    — extracted lead data
    """
    session_id = request.form.get("session_id") or (
        request.get_json(silent=True) or {}
    ).get("session_id", "")
    business_id = safe_int(
        request.form.get("business_id") or (request.get_json(silent=True) or {}).get("business_id"),
        1
    )

    if not session_id:
        return err("session_id is required")

    audio_bytes = None
    audio_filename = "audio.webm"

    # Handle file upload
    if "audio" in request.files:
        file = request.files["audio"]
        audio_bytes = file.read()
        audio_filename = file.filename or "audio.webm"
    elif request.is_json:
        body = request.get_json()
        audio_b64 = body.get("audio_b64", "")
        audio_fmt = body.get("audio_format", "webm")
        audio_filename = f"audio.{audio_fmt}"
        if audio_b64:
            import base64
            if "," in audio_b64:
                audio_b64 = audio_b64.split(",", 1)[1]
            try:
                audio_bytes = base64.b64decode(audio_b64)
            except Exception:
                return err("Invalid base64 audio_b64")

    if not audio_bytes:
        return err("No audio provided. Send audio file or audio_b64")

    try:
        from sonora.voice import process_voice_turn
        result = process_voice_turn(
            audio_bytes=audio_bytes,
            session_id=session_id,
            agent=_agent,
            audio_filename=audio_filename,
            business_id=business_id,
        )
        return ok(
            transcript=result.get("transcript"),
            response=result.get("response_text"),
            audio_b64=result.get("audio_b64"),
            lead_data=result.get("lead_data", {}),
            session_id=session_id,
            success=result.get("success", False),
        )
    except Exception as e:
        logger.error("Voice endpoint error: %s\n%s", e, traceback.format_exc())
        return err("Voice processing error", 500)


# ─────────────────────────────────────────────────────────────────────────────
# TTS — POST /api/tts
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/tts")
@require_json
def tts():
    """
    Convert text to speech using OpenAI TTS (voice: nova).

    Request: { text, voice (optional), format (optional, default 'mp3') }
    Response: audio/mpeg binary, or JSON error
    """
    body = request.get_json()
    text = (body.get("text") or "").strip()
    voice = body.get("voice") or config.TTS_VOICE
    output_format = body.get("format", "mp3")
    as_b64 = body.get("b64", False)

    if not text:
        return err("text is required")
    if len(text) > 4096:
        return err("text must be 4096 characters or fewer")

    audio_bytes, content_type = synthesize_speech(
        text=text, voice=voice, output_format=output_format
    )

    if audio_bytes is None:
        return err("TTS synthesis failed. Check OPENAI_API_KEY configuration.", 503)

    if as_b64:
        import base64
        b64 = base64.b64encode(audio_bytes).decode()
        return ok(
            audio_b64=f"data:{content_type};base64,{b64}",
            voice=voice,
            length_bytes=len(audio_bytes),
        )

    return send_file(
        io.BytesIO(audio_bytes),
        mimetype=content_type,
        as_attachment=False,
        download_name=f"sonora_{voice}.{output_format}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# SMS — POST /api/sms/send
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sms/send")
@require_json
def sms_send():
    """
    Send an SMS via Twilio (graceful fallback if not configured).

    Request: { to, message, lead_id (optional) }
    """
    body = request.get_json()
    to = (body.get("to") or "").strip()
    message = (body.get("message") or "").strip()
    lead_id = body.get("lead_id")

    if not to:
        return err("to (phone number) is required")
    if not message:
        return err("message is required")

    sent = send_sms_twilio(to, message)

    # Log to follow-up queue if lead_id provided
    if lead_id and sent:
        try:
            FollowUpCRM.enqueue(
                lead_id=lead_id,
                follow_up_type="nurture_24h",
                scheduled_at=datetime.utcnow().isoformat(),
                message_template=message,
            )
        except Exception:
            pass

    return ok(sent=sent, to=to, twilio_available=config.has_twilio())


# ─────────────────────────────────────────────────────────────────────────────
# Leads — GET /api/leads, GET/PUT /api/leads/<id>
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/leads")
def get_leads():
    """
    List all leads.
    Query params: business_id, status, source, urgency_min
    """
    business_id = safe_int(request.args.get("business_id"), 1)
    status = request.args.get("status")
    source = request.args.get("source")
    urgency_min = safe_int(request.args.get("urgency_min"), 0)

    leads = LeadCRM.get_all(business_id=business_id, status=status, source=source)

    if urgency_min > 0:
        leads = [l for l in leads if (l.get("urgency_score") or 0) >= urgency_min]

    # Enrich with urgency label
    for lead in leads:
        lead["urgency_label"] = _urgency_label(lead.get("urgency_score", 0))

    return ok(leads=leads, count=len(leads))


@app.get("/api/leads/<int:lead_id>")
def get_lead(lead_id: int):
    lead = LeadCRM.get(lead_id)
    if not lead:
        return err(f"Lead {lead_id} not found", 404)

    # Enrich with appointments and follow-ups
    lead["appointments"] = AppointmentCRM.get_all(lead_id=lead_id)
    lead["urgency_label"] = _urgency_label(lead.get("urgency_score", 0))

    return ok(lead=lead)


@app.put("/api/leads/<int:lead_id>")
@require_json
def update_lead(lead_id: int):
    lead = LeadCRM.get(lead_id)
    if not lead:
        return err(f"Lead {lead_id} not found", 404)

    body = request.get_json()
    allowed = {
        "name","phone","email","address","zip","job_type","system_type",
        "system_age","urgency_score","issue_description","status","source","notes"
    }
    updates = {k: v for k, v in body.items() if k in allowed}

    updated = LeadCRM.update(lead_id, **updates)

    # Sync to GHL if configured
    if config.has_ghl():
        try:
            sync_lead_to_ghl(lead_id)
        except Exception as e:
            logger.warning("GHL lead sync failed: %s", e)

    return ok(lead=updated)


# ─────────────────────────────────────────────────────────────────────────────
# Appointments — GET/POST /api/appointments, PUT /api/appointments/<id>
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/appointments")
def get_appointments():
    """
    List appointments.
    Query params: lead_id, status, upcoming (bool)
    """
    lead_id = request.args.get("lead_id")
    status = request.args.get("status")
    upcoming_only = request.args.get("upcoming", "").lower() == "true"

    if upcoming_only:
        appointments = AppointmentCRM.get_upcoming(business_id=1, limit=50)
    else:
        appointments = AppointmentCRM.get_all(
            lead_id=int(lead_id) if lead_id else None,
            status=status
        )

    return ok(appointments=appointments, count=len(appointments))


@app.post("/api/appointments")
@require_json
def create_appointment():
    """
    Book a new appointment.

    Request: {
        lead_id (int, required),
        scheduled_at (ISO datetime, required),
        job_type,
        tech_assigned,
        duration_hours,
        revenue_estimate,
        notes
    }
    """
    body = request.get_json()
    lead_id = body.get("lead_id")
    scheduled_at = body.get("scheduled_at")

    if not lead_id:
        return err("lead_id is required")
    if not scheduled_at:
        return err("scheduled_at is required (ISO datetime)")

    lead = LeadCRM.get(lead_id)
    if not lead:
        return err(f"Lead {lead_id} not found", 404)

    # Estimate revenue if not provided
    revenue_estimate = body.get("revenue_estimate")
    if revenue_estimate is None:
        business = BusinessCRM.get(lead.get("business_id", 1)) or {}
        job_type = body.get("job_type") or lead.get("job_type", "repair")
        if job_type == "install":
            revenue_estimate = business.get("avg_ticket_install", 4500.0)
        else:
            revenue_estimate = business.get("avg_ticket_repair", 150.0)

    try:
        appointment = AppointmentCRM.create(
            lead_id=lead_id,
            scheduled_at=scheduled_at,
            job_type=body.get("job_type") or lead.get("job_type", "repair"),
            tech_assigned=body.get("tech_assigned", ""),
            duration_hours=float(body.get("duration_hours", 2.0)),
            revenue_estimate=float(revenue_estimate),
            notes=body.get("notes", ""),
        )

        # Schedule reminders
        schedule_appointment_reminders(appointment["id"], scheduled_at, lead_id)

        # Sync to GHL
        if config.has_ghl():
            try:
                sync_appointment_to_ghl(appointment["id"])
            except Exception as e:
                logger.warning("GHL appointment sync failed: %s", e)

        return ok(appointment=appointment), 201

    except Exception as e:
        logger.error("Create appointment error: %s", e)
        return err("Failed to create appointment", 500)


@app.put("/api/appointments/<int:appt_id>")
@require_json
def update_appointment(appt_id: int):
    appointment = AppointmentCRM.get(appt_id)
    if not appointment:
        return err(f"Appointment {appt_id} not found", 404)

    body = request.get_json()
    allowed = {
        "scheduled_at","job_type","tech_assigned","duration_hours",
        "status","revenue_estimate","notes"
    }
    updates = {k: v for k, v in body.items() if k in allowed}

    updated = AppointmentCRM.update(appt_id, **updates)

    # If marked completed, schedule review request
    new_status = updates.get("status")
    if new_status == "completed" and appointment.get("lead_id"):
        try:
            schedule_post_job_review(appointment["lead_id"], appt_id)
            LeadCRM.update(appointment["lead_id"], status="completed")
        except Exception as e:
            logger.warning("Review scheduling error: %s", e)

    return ok(appointment=updated)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard — GET /api/dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard():
    """
    Business growth stats for the Sonora dashboard.

    Returns:
        leads_today          — new leads captured today
        leads_total          — all-time leads
        booked_jobs          — total booked/confirmed appointments
        completed_jobs       — completed appointments
        conversion_rate      — booked / total leads (%)
        revenue_estimate     — total pipeline revenue estimate
        missed_calls_recovered — leads from missed_call source
        follow_up_queue      — pending follow-ups
        review_requests_pending — pending review requests
        upcoming_appointments — next 5 appointments
    """
    business_id = safe_int(request.args.get("business_id"), 1)

    try:
        all_leads = LeadCRM.get_all(business_id=business_id)
        leads_today = LeadCRM.count_today(business_id=business_id)
        leads_total = len(all_leads)

        booked_jobs = AppointmentCRM.count_booked(business_id=business_id)
        revenue_estimate = AppointmentCRM.total_revenue_estimate(business_id=business_id)
        upcoming = AppointmentCRM.get_upcoming(business_id=business_id, limit=5)

        all_appointments = AppointmentCRM.get_all()
        completed_jobs = len([a for a in all_appointments if a.get("status") == "completed"])

        conversion_rate = 0.0
        if leads_total > 0:
            conversion_rate = round((booked_jobs / leads_total) * 100, 1)

        missed_calls_recovered = len([
            l for l in all_leads if l.get("source") == "missed_call"
            and l.get("status") not in ("lost",)
        ])

        follow_up_queue = FollowUpCRM.count_pending()
        review_requests_pending = ReviewCRM.count_pending()

        # Urgency breakdown
        urgency_breakdown = {
            "emergency": len([l for l in all_leads if (l.get("urgency_score") or 0) >= 8]),
            "high":      len([l for l in all_leads if 5 <= (l.get("urgency_score") or 0) < 8]),
            "medium":    len([l for l in all_leads if 3 <= (l.get("urgency_score") or 0) < 5]),
            "low":       len([l for l in all_leads if (l.get("urgency_score") or 0) < 3]),
        }

        # Status breakdown
        status_breakdown = {}
        for lead in all_leads:
            s = lead.get("status", "unknown")
            status_breakdown[s] = status_breakdown.get(s, 0) + 1

        # Job type breakdown
        job_breakdown = {}
        for lead in all_leads:
            jt = lead.get("job_type", "unknown")
            job_breakdown[jt] = job_breakdown.get(jt, 0) + 1

        return ok(
            # Top KPIs
            leads_today=leads_today,
            leads_total=leads_total,
            booked_jobs=booked_jobs,
            completed_jobs=completed_jobs,
            conversion_rate=conversion_rate,
            revenue_estimate=revenue_estimate,
            missed_calls_recovered=missed_calls_recovered,
            follow_up_queue=follow_up_queue,
            review_requests_pending=review_requests_pending,
            # Breakdowns
            urgency_breakdown=urgency_breakdown,
            status_breakdown=status_breakdown,
            job_breakdown=job_breakdown,
            # Upcoming
            upcoming_appointments=upcoming,
            # Timestamp
            as_of=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error("Dashboard error: %s\n%s", e, traceback.format_exc())
        return err("Dashboard data unavailable", 500)


# ─────────────────────────────────────────────────────────────────────────────
# GHL Webhook — POST /api/webhook/ghl
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/webhook/ghl")
def webhook_ghl():
    """
    Receive and process GoHighLevel webhooks.
    Verifies HMAC signature if GHL_WEBHOOK_SECRET is set.
    """
    raw_body = request.get_data()
    signature = request.headers.get("X-GHL-Signature", "")

    if not verify_ghl_webhook_signature(raw_body, signature):
        logger.warning("GHL webhook signature verification failed")
        return err("Invalid signature", 401)

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return err("Invalid JSON payload", 400)

    event_type = data.get("type", data.get("event", "unknown"))
    logger.info("GHL webhook received: type=%s", event_type)

    result = process_ghl_webhook(event_type, data)

    return ok(
        event_type=event_type,
        result=result,
        timestamp=datetime.utcnow().isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reviews — GET /api/reviews
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/reviews")
def get_reviews():
    """Return the review request queue with status."""
    reviews = ReviewCRM.get_all()
    pending = [r for r in reviews if r.get("status") == "pending"]
    sent    = [r for r in reviews if r.get("status") == "sent"]
    done    = [r for r in reviews if r.get("status") in ("completed", "clicked")]

    return ok(
        reviews=reviews,
        count=len(reviews),
        pending=len(pending),
        sent=len(sent),
        completed=len(done),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reactivation — POST /api/reactivate
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/reactivate")
def reactivate():
    """
    Trigger a seasonal reactivation campaign for dormant leads (90+ days).

    Request: { business_id (optional), days_dormant (optional, default 90) }
    """
    body = request.get_json(silent=True) or {}
    business_id = safe_int(body.get("business_id"), 1)
    days = safe_int(body.get("days_dormant"), 90)

    try:
        count = schedule_seasonal_reactivation(business_id=business_id)
        return ok(
            scheduled=count,
            message=f"Queued reactivation messages for {count} dormant customer(s)",
            campaign="seasonal_reactivation",
        )
    except Exception as e:
        logger.error("Reactivation error: %s", e)
        return err("Failed to schedule reactivation campaign", 500)


# ─────────────────────────────────────────────────────────────────────────────
# Follow-Up Queue — GET /api/followups
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/followups")
def get_followups():
    """List all follow-up queue items."""
    items = FollowUpCRM.get_all()
    pending = [i for i in items if i.get("status") == "pending"]
    sent    = [i for i in items if i.get("status") == "sent"]
    failed  = [i for i in items if i.get("status") == "failed"]

    return ok(
        follow_ups=items,
        count=len(items),
        pending=len(pending),
        sent=len(sent),
        failed=len(failed),
    )


@app.post("/api/followups/process")
def process_followups():
    """Manually trigger follow-up processing (useful for testing)."""
    stats = process_due_follow_ups(sms_sender=send_sms_twilio)
    return ok(**stats)


# ─────────────────────────────────────────────────────────────────────────────
# Greeting — GET /api/greeting
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/greeting")
def get_greeting():
    """
    Get Sonora's opening call greeting for a business.
    Optionally returns TTS audio.
    """
    business_id = safe_int(request.args.get("business_id"), 1)
    business = BusinessCRM.get(business_id) or {"name": "Desert Air HVAC"}
    as_audio = request.args.get("audio", "").lower() == "true"

    greeting_text = _agent.get_greeting(business.get("name"))

    response = ok(greeting=greeting_text, business=business.get("name"))

    if as_audio and config.has_openai():
        audio_b64 = synthesize_speech_b64(greeting_text)
        return ok(greeting=greeting_text, business=business.get("name"), audio_b64=audio_b64)

    return response


# ─────────────────────────────────────────────────────────────────────────────
# Businesses — GET /api/businesses
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/businesses")
def get_businesses():
    businesses = BusinessCRM.get_all()
    return ok(businesses=businesses)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _urgency_label(score: int) -> str:
    if score >= 9:  return "EMERGENCY"
    if score >= 7:  return "URGENT"
    if score >= 5:  return "HIGH"
    if score >= 3:  return "MEDIUM"
    return "LOW"


@app.errorhandler(404)
def not_found(e):
    return err("Endpoint not found", 404)


@app.errorhandler(405)
def method_not_allowed(e):
    return err("Method not allowed", 405)


@app.errorhandler(500)
def internal_error(e):
    return err("Internal server error", 500)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=config.DEBUG,
    )
