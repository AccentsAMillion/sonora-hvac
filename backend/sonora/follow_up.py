"""
sonora/follow_up.py — Sonora Automated Follow-Up Engine

Manages the full lifecycle of customer follow-up sequences:
- Missed call recovery (SMS within 2 minutes)
- No-response nurture (24hr, 3-day, 7-day)
- Appointment reminders (24hr before, 2hr before)
- Post-job review requests (4 hours after completion)
- Seasonal reactivation (dormant customers 90+ days)

All messages are generated in Sonora's warm, personal voice.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from config import config
from sonora.crm import (
    LeadCRM, AppointmentCRM, FollowUpCRM, ReviewCRM, BusinessCRM
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Message Templates (used as fallback when OpenAI unavailable)
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = {
    "missed_call": (
        "Hi {first_name}, sorry we missed your call! This is Sonora with {business_name}. "
        "We'd love to help with your HVAC needs — reply here or call us back anytime. 🌡️"
    ),
    "nurture_24h": (
        "Hi {first_name}, this is Sonora with {business_name}. "
        "Just checking in — we know {issue_description_short} can be stressful. "
        "We still have openings this week and would love to help. "
        "Reply or call us back to get scheduled!"
    ),
    "nurture_3d": (
        "Hey {first_name}! Sonora here with {business_name}. "
        "Still thinking about your {system_type} system? "
        "Our techs are in your area this week — let's get you sorted before the weather changes. "
        "Reply here to schedule!"
    ),
    "nurture_7d": (
        "Hi {first_name}, we wanted to reach out one more time. "
        "This is Sonora with {business_name}. "
        "If you haven't solved your {issue_description_short} yet, we're here to help. "
        "Same-week scheduling available. Call or text us anytime!"
    ),
    "appt_reminder_24h": (
        "Hi {first_name}! Quick reminder — your {job_type} appointment with {business_name} "
        "is tomorrow at {appt_time}. Your tech {tech_name} will call when on the way. "
        "Reply CONFIRM or RESCHEDULE if needed. See you tomorrow! 🛠️"
    ),
    "appt_reminder_2h": (
        "Hi {first_name}, heads up — your {business_name} tech is heading your way soon "
        "for your {job_type} appointment. They'll call when about 15-20 minutes out. "
        "Please make sure someone 18+ is home. See you shortly!"
    ),
    "post_job_review": (
        "Hi {first_name}! It was great taking care of your {job_type} today. "
        "If everything is running great, would you mind leaving us a quick Google review? "
        "It takes just 60 seconds and means the world to our small team. "
        "Link: https://g.page/r/{business_name_slug}/review — Thank you so much! — Sonora 💙"
    ),
    "seasonal_reactivation": (
        "Hi {first_name}! This is Sonora with {business_name}. "
        "With {season} around the corner, now is the perfect time for your annual HVAC tune-up — "
        "before the rush! We're booking fast. "
        "Reply to schedule your maintenance visit and keep your system running all {season}. 🏠"
    ),
}


def _current_season() -> str:
    month = datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    elif month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    else:
        return "fall"


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace(",", "").replace(".", "")


# ─────────────────────────────────────────────────────────────────────────────
# AI-Powered Message Generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_message(lead: Dict, follow_up_type: str,
                     business: Optional[Dict] = None,
                     appointment: Optional[Dict] = None) -> str:
    """
    Generate a personalized follow-up message in Sonora's voice.
    Uses GPT-4o when available, falls back to templates.

    Args:
        lead: Lead record dict
        follow_up_type: One of the follow_up_queue type values
        business: Business record dict (fetched if not provided)
        appointment: Appointment record dict (for reminder types)

    Returns:
        Message text ready to send via SMS/email
    """
    if not business:
        business = BusinessCRM.get(lead.get("business_id", 1)) or {
            "name": "Desert Air HVAC",
            "booking_hours": "7am-7pm Mon-Sat",
        }

    # Try AI generation first
    if config.has_openai():
        try:
            ai_message = _ai_generate_message(lead, follow_up_type, business, appointment)
            if ai_message:
                return ai_message
        except Exception as e:
            logger.warning("AI message generation failed, using template: %s", e)

    # Fallback to templates
    return _template_message(lead, follow_up_type, business, appointment)


def _ai_generate_message(lead: Dict, follow_up_type: str,
                         business: Dict, appointment: Optional[Dict]) -> Optional[str]:
    """Generate a personalized message using GPT-4o."""
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    first_name = (lead.get("name") or "").split()[0] or "there"
    business_name = business.get("name", "Desert Air HVAC")

    context = f"""
Lead info:
- Name: {lead.get('name', 'Unknown')}
- Job type: {lead.get('job_type', 'HVAC service')}
- System type: {lead.get('system_type', 'HVAC system')}
- Issue: {lead.get('issue_description', 'not specified')}
- Status: {lead.get('status', 'new')}

Business: {business_name}
Booking hours: {business.get('booking_hours', '7am-7pm Mon-Sat')}
"""
    if appointment:
        appt_dt = appointment.get("scheduled_at", "")
        if appt_dt:
            try:
                dt = datetime.fromisoformat(appt_dt)
                appt_dt = dt.strftime("%A, %B %d at %I:%M %p")
            except Exception:
                pass
        context += f"""
Appointment:
- Date/time: {appt_dt}
- Job: {appointment.get('job_type', '')}
- Tech: {appointment.get('tech_assigned', 'your technician')}
"""

    type_instructions = {
        "missed_call":          "Write a warm missed-call recovery SMS. Keep it under 2 sentences. Friendly, no pressure.",
        "nurture_24h":          "Write a 24-hour check-in SMS. Empathetic, still available. One soft CTA.",
        "nurture_3d":           "Write a 3-day nurture SMS. Create light urgency without being pushy. Mention scheduling.",
        "nurture_7d":           "Write a final nurture SMS. Last outreach, make it count. Honest and warm.",
        "appt_reminder_24h":    "Write a 24-hour appointment reminder SMS. Include date/time, tech name, what to expect.",
        "appt_reminder_2h":     "Write a 2-hour appointment reminder SMS. Tech is on the way soon. Keep it short.",
        "post_job_review":      "Write a post-job review request SMS. Warm and personal. Include that a Google review would mean a lot.",
        "seasonal_reactivation":"Write a seasonal reactivation SMS. Mention the current season and annual tune-up timing.",
    }

    instruction = type_instructions.get(follow_up_type, "Write a helpful HVAC follow-up SMS.")

    prompt = f"""You are Sonora, the AI assistant for {business_name} — an HVAC company. 
You write follow-up SMS messages on behalf of the business. Your voice is warm, confident, melodic, and personal.

{context}

Task: {instruction}

Rules:
- Address the customer by first name ({first_name})
- Keep it under 160 characters (1 SMS) when possible, 2 SMS max
- Sound human, not automated
- Sign off as "Sonora" or "— {business_name}" 
- Do NOT include placeholder brackets like [link] — write actual helpful content
- No emojis unless they feel natural

Write ONLY the message text, nothing else.
"""

    response = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=200,
    )

    return response.choices[0].message.content.strip()


def _template_message(lead: Dict, follow_up_type: str,
                       business: Dict, appointment: Optional[Dict]) -> str:
    """Fill in a template message with lead/business data."""
    first_name = (lead.get("name") or "there").split()[0]
    business_name = business.get("name", "Desert Air HVAC")
    system_type_map = {
        "ac": "AC", "heat": "heating system",
        "heat_pump": "heat pump", "both": "HVAC system", "unknown": "HVAC system"
    }
    job_type_map = {
        "repair": "repair", "install": "installation",
        "maintenance": "maintenance", "emergency": "emergency repair", "unknown": "service"
    }

    issue = lead.get("issue_description") or f"{system_type_map.get(lead.get('system_type','unknown'),'HVAC system')} issue"
    short_issue = issue[:50] + "..." if len(issue) > 50 else issue

    tech_name = "your technician"
    appt_time = "your scheduled time"
    appt_job = job_type_map.get(lead.get("job_type", "unknown"), "service")

    if appointment:
        tech_name = appointment.get("tech_assigned") or "your technician"
        try:
            dt = datetime.fromisoformat(appointment.get("scheduled_at", ""))
            appt_time = dt.strftime("%I:%M %p")
            appt_job = job_type_map.get(appointment.get("job_type", ""), "service")
        except Exception:
            pass

    template = TEMPLATES.get(follow_up_type, TEMPLATES["nurture_24h"])

    return template.format(
        first_name=first_name,
        business_name=business_name,
        business_name_slug=_slug(business_name),
        system_type=system_type_map.get(lead.get("system_type", "unknown"), "HVAC system"),
        job_type=appt_job,
        issue_description_short=short_issue,
        tech_name=tech_name,
        appt_time=appt_time,
        season=_current_season(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Follow-Up Scheduling Helpers
# ─────────────────────────────────────────────────────────────────────────────

def schedule_missed_call_sequence(lead_id: int):
    """
    Schedule the full missed-call recovery + nurture sequence.
    - T+2 min:  Missed call SMS
    - T+24 hr:  Nurture 24h
    - T+3 days: Nurture 3-day
    - T+7 days: Nurture 7-day
    """
    now = datetime.utcnow()
    sequence = [
        ("missed_call",   now + timedelta(seconds=config.MISSED_CALL_DELAY_SECONDS)),
        ("nurture_24h",   now + timedelta(hours=24)),
        ("nurture_3d",    now + timedelta(days=3)),
        ("nurture_7d",    now + timedelta(days=7)),
    ]
    for follow_up_type, scheduled_at in sequence:
        try:
            FollowUpCRM.enqueue(
                lead_id=lead_id,
                follow_up_type=follow_up_type,
                scheduled_at=scheduled_at.isoformat(),
            )
        except Exception as e:
            logger.error("Error scheduling %s for lead %d: %s", follow_up_type, lead_id, e)

    logger.info("Scheduled missed-call sequence for lead %d", lead_id)


def schedule_appointment_reminders(appointment_id: int, scheduled_at: str, lead_id: int):
    """
    Schedule appointment reminders:
    - 24 hours before
    - 2 hours before
    """
    try:
        appt_dt = datetime.fromisoformat(scheduled_at)
        reminders = [
            ("appt_reminder_24h", appt_dt - timedelta(hours=24)),
            ("appt_reminder_2h",  appt_dt - timedelta(hours=2)),
        ]
        now = datetime.utcnow()
        for follow_up_type, reminder_dt in reminders:
            if reminder_dt > now:  # Only schedule future reminders
                FollowUpCRM.enqueue(
                    lead_id=lead_id,
                    follow_up_type=follow_up_type,
                    scheduled_at=reminder_dt.isoformat(),
                )
        logger.info("Scheduled appointment reminders for appointment %d", appointment_id)
    except Exception as e:
        logger.error("Error scheduling appointment reminders: %s", e)


def schedule_post_job_review(lead_id: int, appointment_id: int):
    """Schedule a review request 4 hours after job completion."""
    try:
        scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()
        FollowUpCRM.enqueue(
            lead_id=lead_id,
            follow_up_type="post_job_review",
            scheduled_at=scheduled_at,
        )
        # Also create a review record
        ReviewCRM.create(lead_id=lead_id, appointment_id=appointment_id, platform="google")
        logger.info("Scheduled post-job review request for lead %d", lead_id)
    except Exception as e:
        logger.error("Error scheduling review request: %s", e)


def schedule_seasonal_reactivation(business_id: int = 1):
    """
    Schedule seasonal reactivation messages for all dormant customers (90+ days).
    Run this quarterly or at the start of AC season / heating season.
    """
    dormant_leads = LeadCRM.get_dormant(business_id=business_id, days=90)
    scheduled_count = 0

    now = datetime.utcnow()
    for i, lead in enumerate(dormant_leads):
        # Stagger sends by 5 minutes each to avoid spam signals
        scheduled_at = (now + timedelta(minutes=i * 5)).isoformat()
        try:
            FollowUpCRM.enqueue(
                lead_id=lead["id"],
                follow_up_type="seasonal_reactivation",
                scheduled_at=scheduled_at,
            )
            scheduled_count += 1
        except Exception as e:
            logger.error("Error scheduling reactivation for lead %d: %s", lead["id"], e)

    logger.info("Scheduled %d seasonal reactivation messages for business %d",
                scheduled_count, business_id)
    return scheduled_count


# ─────────────────────────────────────────────────────────────────────────────
# Follow-Up Processor (runs on a schedule)
# ─────────────────────────────────────────────────────────────────────────────

def process_due_follow_ups(sms_sender=None) -> Dict[str, int]:
    """
    Fetch all due follow-ups and process them.
    Called by the APScheduler job every minute.

    Args:
        sms_sender: callable(phone, message) → bool, or None for dry-run

    Returns:
        Stats dict: {processed, sent, failed, skipped}
    """
    stats = {"processed": 0, "sent": 0, "failed": 0, "skipped": 0}
    due_items = FollowUpCRM.get_due(limit=50)

    for item in due_items:
        stats["processed"] += 1
        lead_id = item.get("lead_id")
        follow_up_type = item.get("follow_up_type")
        fq_id = item.get("id")

        try:
            # Build lead dict from joined query result
            lead = {
                "id": lead_id,
                "name": item.get("name"),
                "phone": item.get("phone"),
                "email": item.get("email"),
                "job_type": item.get("job_type"),
                "system_type": item.get("system_type"),
                "issue_description": item.get("issue_description"),
                "business_id": item.get("business_id", 1),
            }
            phone = lead.get("phone")

            if not phone:
                logger.warning("No phone for lead %d follow-up %d — skipping", lead_id, fq_id)
                FollowUpCRM.mark_failed(fq_id)
                stats["skipped"] += 1
                continue

            # Get appointment for reminder types
            appointment = None
            if follow_up_type in ("appt_reminder_24h", "appt_reminder_2h"):
                appts = AppointmentCRM.get_all(lead_id=lead_id, status="scheduled")
                appointment = appts[0] if appts else None

            # Generate the message
            message = generate_message(
                lead=lead,
                follow_up_type=follow_up_type,
                appointment=appointment,
            )

            # Send via SMS
            sent = False
            if sms_sender and callable(sms_sender):
                sent = sms_sender(phone, message)
            else:
                # No sender configured — log as if sent (dev mode)
                logger.info("[DRY RUN] Would send SMS to %s:\n%s", phone, message)
                sent = True  # Count as sent in dev mode

            if sent:
                FollowUpCRM.mark_sent(fq_id)
                stats["sent"] += 1
                logger.info("Follow-up sent: type=%s lead=%d", follow_up_type, lead_id)
            else:
                FollowUpCRM.mark_failed(fq_id)
                stats["failed"] += 1

        except Exception as e:
            logger.error("Error processing follow-up %d: %s", fq_id, e)
            try:
                FollowUpCRM.mark_failed(fq_id)
            except Exception:
                pass
            stats["failed"] += 1

    if stats["processed"] > 0:
        logger.info("Follow-up batch complete: %s", stats)

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# APScheduler Setup
# ─────────────────────────────────────────────────────────────────────────────

_scheduler = None


def start_followup_scheduler(sms_sender=None):
    """
    Start the APScheduler background job for automated follow-ups.
    Safe to call multiple times — idempotent.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("Follow-up scheduler already running")
        return _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            func=lambda: process_due_follow_ups(sms_sender=sms_sender),
            trigger="interval",
            seconds=config.FOLLOWUP_ENGINE_INTERVAL_SECONDS,
            id="sonora_followup_engine",
            name="Sonora Follow-Up Engine",
            replace_existing=True,
            misfire_grace_time=30,
        )
        _scheduler.start()
        logger.info(
            "Sonora follow-up scheduler started (interval: %ds)",
            config.FOLLOWUP_ENGINE_INTERVAL_SECONDS,
        )
        return _scheduler

    except ImportError:
        logger.warning("APScheduler not installed — follow-up engine disabled. "
                       "Install with: pip install APScheduler")
        return None
    except Exception as e:
        logger.error("Failed to start follow-up scheduler: %s", e)
        return None


def stop_followup_scheduler():
    """Stop the follow-up scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Follow-up scheduler stopped")
