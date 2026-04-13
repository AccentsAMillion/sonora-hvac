"""
sonora/ghl.py — GoHighLevel (GHL) Integration
Syncs Sonora leads and appointments to GHL CRM.
Processes inbound GHL webhooks (missed call, form submission, etc.)
Degrades gracefully when credentials are not configured.
"""

import hmac
import hashlib
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests

from config import config
from sonora.crm import LeadCRM, AppointmentCRM, FollowUpCRM
from sonora.follow_up import schedule_missed_call_sequence

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# GHL API Client
# ─────────────────────────────────────────────────────────────────────────────

GHL_API_BASE = "https://rest.gohighlevel.com/v1"
GHL_API_V2_BASE = "https://services.leadconnectorhq.com"


class GHLClient:
    """
    GoHighLevel API client.
    All methods degrade gracefully (return None / empty dict) when not configured.
    """

    def __init__(self):
        self.api_key = config.GHL_API_KEY
        self.location_id = config.GHL_LOCATION_ID
        self.available = config.has_ghl()

        if not self.available:
            logger.info("GoHighLevel not configured — integration disabled. "
                        "Set GHL_API_KEY and GHL_LOCATION_ID in .env to enable.")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Version": "2021-07-28",
        }

    def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        if not self.available:
            return None
        try:
            url = f"{GHL_API_BASE}{path}"
            r = requests.get(url, headers=self._headers, params=params or {}, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error("GHL GET %s error: %s", path, e)
            return None

    def _post(self, path: str, data: Dict) -> Optional[Dict]:
        if not self.available:
            return None
        try:
            url = f"{GHL_API_BASE}{path}"
            r = requests.post(url, headers=self._headers, json=data, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error("GHL POST %s error: %s", path, e)
            return None

    def _put(self, path: str, data: Dict) -> Optional[Dict]:
        if not self.available:
            return None
        try:
            url = f"{GHL_API_BASE}{path}"
            r = requests.put(url, headers=self._headers, json=data, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error("GHL PUT %s error: %s", path, e)
            return None

    # ── Contacts ──────────────────────────────────────────────────────────────

    def upsert_contact(self, lead: Dict) -> Optional[str]:
        """
        Create or update a GHL contact from a Sonora lead.
        Returns the GHL contact ID on success.
        """
        if not self.available:
            return None

        phone = lead.get("phone", "")
        name = lead.get("name", "")
        first_name = name.split()[0] if name else ""
        last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

        # Custom fields for HVAC data
        custom_fields = []
        if lead.get("job_type"):
            custom_fields.append({"key": "hvac_job_type", "value": lead["job_type"]})
        if lead.get("system_type"):
            custom_fields.append({"key": "hvac_system_type", "value": lead["system_type"]})
        if lead.get("urgency_score") is not None:
            custom_fields.append({"key": "hvac_urgency_score",
                                   "value": str(lead["urgency_score"])})
        if lead.get("issue_description"):
            custom_fields.append({"key": "hvac_issue", "value": lead["issue_description"]})

        payload = {
            "locationId": self.location_id,
            "firstName": first_name,
            "lastName": last_name,
            "phone": phone,
            "email": lead.get("email", ""),
            "address1": lead.get("address", ""),
            "postalCode": lead.get("zip", ""),
            "source": f"Sonora - {lead.get('source', 'inbound_call')}",
            "tags": self._build_tags(lead),
            "customField": custom_fields,
        }

        # Remove empty values
        payload = {k: v for k, v in payload.items() if v}

        result = self._post("/contacts/", payload)
        if result and result.get("contact", {}).get("id"):
            ghl_id = result["contact"]["id"]
            logger.info("GHL contact created/updated: %s → %s", name, ghl_id)
            return ghl_id

        return None

    def _build_tags(self, lead: Dict) -> List[str]:
        tags = ["sonora-lead"]
        if lead.get("job_type") and lead["job_type"] != "unknown":
            tags.append(f"job-{lead['job_type']}")
        if lead.get("urgency_score", 0) >= 8:
            tags.append("urgent")
        if lead.get("source"):
            tags.append(f"source-{lead['source']}")
        if lead.get("status"):
            tags.append(f"status-{lead['status']}")
        return tags

    def get_contact_by_phone(self, phone: str) -> Optional[Dict]:
        """Look up a GHL contact by phone number."""
        result = self._get("/contacts/", params={
            "locationId": self.location_id,
            "query": phone,
        })
        if result and result.get("contacts"):
            return result["contacts"][0]
        return None

    # ── Appointments / Calendar ───────────────────────────────────────────────

    def create_appointment(self, appointment: Dict, contact_id: str,
                           calendar_id: Optional[str] = None) -> Optional[str]:
        """
        Sync a Sonora appointment to GHL calendar.
        Returns GHL appointment ID on success.
        """
        if not self.available or not contact_id:
            return None

        try:
            scheduled_at = appointment.get("scheduled_at", "")
            # GHL expects ISO 8601 with timezone
            if scheduled_at and "T" in scheduled_at:
                if not scheduled_at.endswith("Z") and "+" not in scheduled_at:
                    scheduled_at += "Z"

            payload = {
                "calendarId": calendar_id or "",
                "locationId": self.location_id,
                "contactId": contact_id,
                "startTime": scheduled_at,
                "title": f"HVAC {appointment.get('job_type', 'Service')} — Sonora Booking",
                "appointmentStatus": "confirmed",
                "assignedUserId": "",
                "notes": appointment.get("notes", ""),
            }

            result = self._post("/appointments/", payload)
            if result and result.get("id"):
                logger.info("GHL appointment created: %s", result["id"])
                return result["id"]
        except Exception as e:
            logger.error("Error creating GHL appointment: %s", e)

        return None

    # ── Opportunities (Pipeline) ───────────────────────────────────────────────

    def create_opportunity(self, lead: Dict, contact_id: str,
                           pipeline_id: Optional[str] = None) -> Optional[str]:
        """Create a pipeline opportunity from a lead."""
        if not self.available or not contact_id:
            return None

        try:
            # Revenue estimate based on job type
            monetary_value = 150.0  # default service call
            if lead.get("job_type") == "install":
                monetary_value = 4500.0
            elif lead.get("job_type") == "repair":
                monetary_value = 350.0
            elif lead.get("job_type") == "emergency":
                monetary_value = 500.0

            payload = {
                "pipelineId": pipeline_id or "",
                "locationId": self.location_id,
                "name": f"HVAC {lead.get('job_type', 'Service')} — {lead.get('name', 'New Lead')}",
                "contactId": contact_id,
                "monetaryValue": monetary_value,
                "status": "open",
            }

            result = self._post("/opportunities/", payload)
            if result and result.get("opportunity", {}).get("id"):
                opp_id = result["opportunity"]["id"]
                logger.info("GHL opportunity created: %s", opp_id)
                return opp_id
        except Exception as e:
            logger.error("Error creating GHL opportunity: %s", e)

        return None

    # ── SMS via GHL ───────────────────────────────────────────────────────────

    def send_sms(self, contact_id: str, message: str) -> bool:
        """Send an SMS through GHL's messaging."""
        if not self.available or not contact_id:
            return False
        try:
            result = self._post(f"/conversations/messages", {
                "type": "SMS",
                "contactId": contact_id,
                "locationId": self.location_id,
                "message": message,
            })
            return bool(result)
        except Exception as e:
            logger.error("GHL SMS send error: %s", e)
            return False

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        return {
            "configured": self.available,
            "location_id": self.location_id[:8] + "..." if self.location_id else None,
        }


# Singleton GHL client
_ghl_client = GHLClient()


# ─────────────────────────────────────────────────────────────────────────────
# Sync Functions
# ─────────────────────────────────────────────────────────────────────────────

def sync_lead_to_ghl(lead_id: int) -> Optional[str]:
    """
    Sync a Sonora lead to GHL as a contact.
    Returns GHL contact ID.
    """
    lead = LeadCRM.get(lead_id)
    if not lead:
        logger.warning("Lead %d not found for GHL sync", lead_id)
        return None

    return _ghl_client.upsert_contact(lead)


def sync_appointment_to_ghl(appointment_id: int,
                              ghl_contact_id: Optional[str] = None) -> Optional[str]:
    """
    Sync a Sonora appointment to GHL calendar.
    Automatically syncs the lead to GHL if contact ID not provided.
    """
    appointment = AppointmentCRM.get(appointment_id)
    if not appointment:
        logger.warning("Appointment %d not found for GHL sync", appointment_id)
        return None

    if not ghl_contact_id and appointment.get("lead_id"):
        ghl_contact_id = sync_lead_to_ghl(appointment["lead_id"])

    if not ghl_contact_id:
        logger.warning("No GHL contact ID for appointment %d", appointment_id)
        return None

    return _ghl_client.create_appointment(appointment, ghl_contact_id)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Processing
# ─────────────────────────────────────────────────────────────────────────────

def verify_ghl_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify the HMAC signature on an inbound GHL webhook.
    Returns True if valid or if webhook secret is not configured.
    """
    if not config.GHL_WEBHOOK_SECRET:
        return True  # Not configured — accept all (dev mode)

    try:
        expected = hmac.new(
            config.GHL_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error("Webhook signature verification error: %s", e)
        return False


def process_ghl_webhook(event_type: str, data: Dict) -> Dict:
    """
    Process an inbound GHL webhook event and take action in Sonora.

    Supported event types:
    - InboundMessage / MissedCall → create/update lead, schedule missed-call sequence
    - FormSubmit / WebFormSubmit  → create lead from form data
    - AppointmentStatusChanged    → sync appointment status back to Sonora
    - ContactCreate               → no-op (Sonora is source of truth)

    Returns a result dict for logging/response.
    """
    result = {"handled": False, "action": None, "lead_id": None}

    try:
        if event_type in ("MissedCall", "InboundMessage"):
            result.update(_handle_missed_call(data))

        elif event_type in ("FormSubmit", "WebFormSubmit", "ContactCreate"):
            result.update(_handle_form_submission(data))

        elif event_type == "AppointmentStatusChanged":
            result.update(_handle_appointment_status_change(data))

        else:
            logger.info("Unhandled GHL event type: %s", event_type)
            result["action"] = "ignored"
            result["handled"] = True

    except Exception as e:
        logger.error("Error processing GHL webhook %s: %s", event_type, e)
        result["error"] = str(e)

    return result


def _handle_missed_call(data: Dict) -> Dict:
    """Handle a missed call notification from GHL."""
    phone = data.get("phone", data.get("from", ""))
    name = data.get("contactName", data.get("name", ""))
    business_id = 1  # TODO: resolve from GHL location ID

    # Check if we already have this lead
    existing = LeadCRM.get_by_phone(phone) if phone else None

    if existing:
        lead_id = existing["id"]
        # Escalate to missed_call source if was new
        if existing.get("status") == "new":
            LeadCRM.update(lead_id, source="missed_call", status="contacted")
    else:
        # Create new lead
        new_lead = LeadCRM.create(
            business_id=business_id,
            name=name,
            phone=phone,
            source="missed_call",
            status="contacted",
        )
        lead_id = new_lead["id"] if new_lead else None

    if lead_id:
        schedule_missed_call_sequence(lead_id)
        logger.info("Missed call processed for lead %d (phone: %s)", lead_id, phone)

    return {"handled": True, "action": "missed_call_processed", "lead_id": lead_id}


def _handle_form_submission(data: Dict) -> Dict:
    """Handle a web form submission from GHL."""
    # Map GHL form fields to Sonora lead fields
    name = data.get("full_name") or data.get("name") or (
        f"{data.get('first_name','')} {data.get('last_name','')}".strip()
    )
    phone = data.get("phone", "")
    email = data.get("email", "")
    message = data.get("message", data.get("notes", ""))
    zip_code = data.get("postal_code", data.get("zip", ""))

    new_lead = LeadCRM.create(
        business_id=1,
        name=name,
        phone=phone,
        email=email,
        zip=zip_code,
        issue_description=message,
        source="web_form",
        status="new",
    )
    lead_id = new_lead["id"] if new_lead else None

    if lead_id and phone:
        # Schedule nurture sequence for web leads
        from datetime import timedelta
        from sonora.crm import FollowUpCRM
        from datetime import datetime
        FollowUpCRM.enqueue(
            lead_id=lead_id,
            follow_up_type="nurture_24h",
            scheduled_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
        )

    return {"handled": True, "action": "web_form_lead_created", "lead_id": lead_id}


def _handle_appointment_status_change(data: Dict) -> Dict:
    """Sync appointment status changes from GHL back to Sonora."""
    # In GHL, appointments have their own IDs — match by lead phone
    phone = data.get("phone", "")
    status_map = {
        "confirmed": "confirmed",
        "cancelled": "cancelled",
        "no_show": "no_show",
        "showed": "completed",
    }
    ghl_status = data.get("appointmentStatus", "")
    sonora_status = status_map.get(ghl_status, "")

    if not sonora_status:
        return {"handled": True, "action": "status_ignored"}

    # Find lead by phone and update their appointment
    lead = LeadCRM.get_by_phone(phone) if phone else None
    if lead:
        appointments = AppointmentCRM.get_all(lead_id=lead["id"])
        if appointments:
            appt = appointments[0]
            AppointmentCRM.update(appt["id"], status=sonora_status)

            # If completed, schedule review request
            if sonora_status == "completed":
                from sonora.follow_up import schedule_post_job_review
                schedule_post_job_review(lead["id"], appt["id"])

            return {"handled": True, "action": "appointment_status_synced",
                    "lead_id": lead["id"]}

    return {"handled": True, "action": "appointment_not_found"}


# ─────────────────────────────────────────────────────────────────────────────
# GHL Health / Status
# ─────────────────────────────────────────────────────────────────────────────

def ghl_status() -> Dict:
    """Return GHL integration status."""
    return _ghl_client.health_check()
