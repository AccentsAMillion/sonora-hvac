"""
sonora/agent.py — Sonora AI Brain
"The Voice of Your Business"

Sonora is a warm, confident, melodic AI voice agent for HVAC businesses.
She answers every call, qualifies every lead, books jobs, and runs the
growth engine 24/7 without extra staff.

Conversation State Machine:
  GREETING → QUALIFICATION → URGENCY_CHECK → BOOKING → CONFIRMATION
           → FOLLOW_UP → REVIEW_REQUEST
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from config import config
from sonora.crm import (
    LeadCRM, ConversationCRM, AppointmentCRM, FollowUpCRM, BusinessCRM
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Conversation States
# ─────────────────────────────────────────────────────────────────────────────

class State:
    GREETING        = "GREETING"
    QUALIFICATION   = "QUALIFICATION"
    URGENCY_CHECK   = "URGENCY_CHECK"
    BOOKING         = "BOOKING"
    CONFIRMATION    = "CONFIRMATION"
    FOLLOW_UP       = "FOLLOW_UP"
    REVIEW_REQUEST  = "REVIEW_REQUEST"
    EMERGENCY       = "EMERGENCY"
    CLOSED          = "CLOSED"


# ─────────────────────────────────────────────────────────────────────────────
# Urgency Scoring Reference
# ─────────────────────────────────────────────────────────────────────────────

URGENCY_KEYWORDS = {
    10: ["carbon monoxide", "co detector", "gas leak", "no ac", "not cooling", "not working at all",
         "completely out", "not turning on", "dead", "won't start", "smoke"],
    9:  ["no heat", "freezing", "pipes might freeze", "heat is out", "furnace out"],
    8:  ["barely cooling", "barely heating", "thermostat blank", "tripping breaker", "circuit breaker"],
    7:  ["not cooling well", "not heating well", "blowing warm", "blowing cold"],
    6:  ["water leak", "dripping", "ice on unit", "weird noise", "loud noise"],
    5:  ["strange smell", "burning smell", "high electric bill", "running constantly"],
    4:  ["some rooms not cooling", "uneven temps", "filter check"],
    3:  ["annual maintenance", "yearly checkup", "want an inspection"],
    2:  ["tune-up", "maintenance", "seasonal checkup"],
    1:  ["question", "pricing", "estimate", "just curious"],
}

def compute_urgency_score(issue_description: str, job_type: str) -> int:
    """Score urgency 1-10 based on issue keywords and job type."""
    text = issue_description.lower()
    for score in sorted(URGENCY_KEYWORDS.keys(), reverse=True):
        for kw in URGENCY_KEYWORDS[score]:
            if kw in text:
                return score
    # Fallback by job type
    job_scores = {"emergency": 9, "repair": 5, "install": 3, "maintenance": 2, "unknown": 3}
    return job_scores.get(job_type, 3)


# ─────────────────────────────────────────────────────────────────────────────
# GPT-4o Function Definitions for Structured Lead Extraction
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_LEAD_FUNCTION = {
    "name": "extract_lead_data",
    "description": "Extract structured lead qualification data from the conversation. Call this whenever new information about the customer is learned.",
    "parameters": {
        "type": "object",
        "properties": {
            "name":              {"type": "string",  "description": "Customer's full name"},
            "phone":             {"type": "string",  "description": "Customer's phone number"},
            "email":             {"type": "string",  "description": "Customer's email address"},
            "address":           {"type": "string",  "description": "Service address"},
            "zip":               {"type": "string",  "description": "ZIP code"},
            "job_type":          {"type": "string",  "enum": ["repair","install","maintenance","emergency","unknown"]},
            "system_type":       {"type": "string",  "enum": ["ac","heat","heat_pump","both","unknown"]},
            "system_age":        {"type": "integer", "description": "Approximate age of HVAC system in years"},
            "issue_description": {"type": "string",  "description": "Description of the HVAC problem or service needed"},
            "urgency_score":     {"type": "integer", "description": "Urgency 1-10 (10=carbon monoxide/no AC in heat, 9=no heat in winter, 2=routine tune-up)"},
            "ready_to_book":     {"type": "boolean", "description": "Whether the customer is ready to schedule an appointment"},
        },
        "required": []
    }
}

UPDATE_STATE_FUNCTION = {
    "name": "update_conversation_state",
    "description": "Signal a state transition in the conversation flow.",
    "parameters": {
        "type": "object",
        "properties": {
            "new_state": {
                "type": "string",
                "enum": [State.GREETING, State.QUALIFICATION, State.URGENCY_CHECK,
                         State.BOOKING, State.CONFIRMATION, State.FOLLOW_UP,
                         State.REVIEW_REQUEST, State.EMERGENCY, State.CLOSED],
                "description": "The conversation state to transition to"
            },
            "reason": {"type": "string"}
        },
        "required": ["new_state"]
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# Sonora System Prompt
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(business_name: str = "Desert Air HVAC",
                        booking_hours: str = "7am-7pm Mon-Sat",
                        state: str = State.GREETING,
                        lead_data: Optional[Dict] = None) -> str:

    lead_summary = ""
    if lead_data:
        collected = [f"- {k}: {v}" for k, v in lead_data.items() if v]
        if collected:
            lead_summary = "\n\nINFORMATION ALREADY COLLECTED:\n" + "\n".join(collected)

    return f"""You are Sonora — the AI voice agent and business assistant for {business_name}. 
You are "The Voice of the Business." You are NOT a bot — you ARE Sonora.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SONORA'S PERSONALITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Tone: Confident, warm, melodic, empathetic — you make every homeowner feel heard and cared for
• You speak with urgency for emergencies and calm reassurance for routine jobs
• You never say you're a bot, AI, or automated system — you ARE Sonora
• You're an HVAC expert who knows systems, common failures, seasonal patterns, and realistic pricing
• You ask one question at a time — never overwhelm with multiple questions
• You mirror the customer's energy: urgent when they're stressed, conversational when they're relaxed
• You're the best thing that ever happened to this business and to this customer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HVAC EXPERTISE (know this cold)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Common repairs: capacitor ($150-350), refrigerant recharge ($250-500), blower motor ($300-600),
  compressor ($800-2500), heat exchanger ($600-1500)
• Installs: single-zone split ($3,500-6,000), whole-home central AC ($4,000-7,500),
  heat pump ($4,500-8,000), furnace ($2,500-5,000)
• Maintenance: tune-up/safety check ($89-149), filter replacement, coil cleaning
• System lifespan: AC 15-20 yrs, furnace 20-25 yrs, heat pump 15 yrs
• URGENT red flags: no cooling above 90°F, no heat below 40°F, CO detector alarm, burning smell,
  complete system failure, breaker keeps tripping

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSATION STATE: {state}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GREETING: Open with warmth. Introduce yourself. Ask for their name and what's going on.
  Example: "Hi, thanks for calling {business_name}! This is Sonora — I'm here to help get you 
  taken care of today. Can I start with your name and tell me what's going on with your system?"

QUALIFICATION: Gather lead info naturally — one question at a time:
  1. Name ✓  2. What's happening with the system?  3. What type of system?
  4. How old is it approximately?  5. Address / zip code?

URGENCY_CHECK: Assess urgency. For emergencies (score 8-10), switch to EMERGENCY flow.
  Ask: "Is this completely out, or is it still somewhat working?"
  For scores ≥8: "I hear you — that sounds like it needs attention right away. 
  Let me get someone to you as fast as possible."

EMERGENCY: Use urgency. Escalate immediately.
  "I'm getting someone to you as fast as possible. I need your address — 
  we'll have a tech heading your way within the hour."

BOOKING: Guide to appointment. Suggest specific slots.
  "Perfect — we have availability [tomorrow morning / this afternoon]. 
  Which works better for you?" Confirm the slot.

CONFIRMATION: Confirm everything. Set expectations.
  "You're all set! Your [job_type] appointment is scheduled for [date/time]. 
  Your tech will call when they're on the way. Is there anything else?"

FOLLOW_UP: After the job, check in.
  "Hi [name], just checking in — how did everything go with the service? 
  Is your system running the way it should?"

REVIEW_REQUEST: Warm, personal review ask.
  "I'm so glad we could take care of that for you! If you have a moment, 
  a quick Google review would mean the world to us — it helps other families 
  in [city] find us when they need help most."
{lead_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Business hours for booking: {booking_hours}
• Never give a definitive price — say "typically runs $X-Y, but your tech will confirm on-site"
• Always call the extract_lead_data function when you learn new information about the customer
• Always call update_conversation_state when the conversation stage shifts
• Keep responses conversational and under 3 sentences unless explaining something important
• You can handle multiple callers simultaneously — each session_id is independent
• If someone asks about pricing, give realistic HVAC ranges but emphasize the free diagnosis
"""


# ─────────────────────────────────────────────────────────────────────────────
# Session Memory
# ─────────────────────────────────────────────────────────────────────────────

class SessionMemory:
    """In-process session state store."""

    def __init__(self):
        self._sessions: Dict[str, Dict] = {}

    def get(self, session_id: str) -> Dict:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "state": State.GREETING,
                "lead_data": {},
                "lead_id": None,
                "business_id": 1,
                "messages": [],   # OpenAI message history
                "turn_count": 0,
            }
        return self._sessions[session_id]

    def update(self, session_id: str, **kwargs):
        session = self.get(session_id)
        session.update(kwargs)

    def update_lead_data(self, session_id: str, extracted: Dict):
        session = self.get(session_id)
        # Merge — only overwrite with non-None, non-empty values
        for k, v in extracted.items():
            if v is not None and v != "" and v != "unknown":
                session["lead_data"][k] = v

    def append_message(self, session_id: str, role: str, content: str):
        session = self.get(session_id)
        session["messages"].append({"role": role, "content": content})
        # Keep last 20 messages in context (rolling window)
        if len(session["messages"]) > 20:
            session["messages"] = session["messages"][-20:]

    def get_openai_messages(self, session_id: str) -> List[Dict]:
        session = self.get(session_id)
        return session["messages"]

    def clear(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]


# Singleton session store
_session_memory = SessionMemory()


# ─────────────────────────────────────────────────────────────────────────────
# Sonora Agent
# ─────────────────────────────────────────────────────────────────────────────

class SonoraAgent:
    """
    The Sonora AI brain. Each call to .chat() drives the conversation forward,
    extracts lead data, manages state transitions, and persists everything to
    the CRM automatically.
    """

    def __init__(self, business_id: int = 1):
        self.business_id = business_id
        self._client = None
        self._available = config.has_openai()

        if self._available:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=config.OPENAI_API_KEY)
            except ImportError:
                logger.warning("openai package not installed — Sonora running in demo mode")
                self._available = False

        # Load business info
        self._business = BusinessCRM.get(business_id) or {
            "name": "Desert Air HVAC",
            "booking_hours": "7am-7pm Mon-Sat",
        }

    def chat(self, session_id: str, message: str,
             business_id: Optional[int] = None) -> Tuple[str, Dict]:
        """
        Process a user message and return (response_text, lead_data).
        Persists conversation and any extracted lead data to the CRM.
        """
        if business_id:
            self.business_id = business_id

        session = _session_memory.get(session_id)
        session["turn_count"] += 1

        # Log to CRM conversation
        ConversationCRM.append_message(session_id, "user", message,
                                       lead_id=session.get("lead_id"))

        if not self._available:
            return self._demo_response(session_id, message, session)

        # Build system prompt with current state + collected lead data
        system_prompt = build_system_prompt(
            business_name=self._business.get("name", "Desert Air HVAC"),
            booking_hours=self._business.get("booking_hours", "7am-7pm Mon-Sat"),
            state=session["state"],
            lead_data=session["lead_data"]
        )

        # Append user message to OpenAI history
        _session_memory.append_message(session_id, "user", message)

        # Build messages list for API call
        messages = [{"role": "system", "content": system_prompt}] + \
                   _session_memory.get_openai_messages(session_id)

        try:
            response = self._client.chat.completions.create(
                model=config.OPENAI_CHAT_MODEL,
                messages=messages,
                tools=[
                    {"type": "function", "function": EXTRACT_LEAD_FUNCTION},
                    {"type": "function", "function": UPDATE_STATE_FUNCTION},
                ],
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500,
            )

            reply_text, extracted_lead, new_state = self._process_response(
                response, session_id, session
            )

        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            reply_text = self._fallback_response(session["state"])
            extracted_lead = {}
            new_state = None

        # Apply state transition
        if new_state and new_state != session["state"]:
            _session_memory.update(session_id, state=new_state)
            session = _session_memory.get(session_id)

        # Persist/update lead in CRM
        lead_data = session["lead_data"]
        lead_id = self._upsert_lead(session_id, session, lead_data)

        # Log assistant response to CRM
        ConversationCRM.append_message(session_id, "assistant", reply_text,
                                       lead_id=lead_id)
        _session_memory.append_message(session_id, "assistant", reply_text)

        # Auto-schedule missed-call SMS if this is a missed call recovery
        if session.get("source") == "missed_call" and session["turn_count"] == 1:
            self._schedule_missed_call_followup(lead_id, lead_data)

        return reply_text, {**lead_data, "lead_id": lead_id, "state": session["state"]}

    def _process_response(self, response, session_id: str, session: Dict):
        """Parse OpenAI response including any function calls."""
        extracted_lead = {}
        new_state = None
        reply_text = ""

        msg = response.choices[0].message

        # Handle tool calls
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if fn_name == "extract_lead_data":
                    extracted_lead = args
                    _session_memory.update_lead_data(session_id, args)
                    # Auto-compute urgency if description provided
                    if args.get("issue_description") and not args.get("urgency_score"):
                        score = compute_urgency_score(
                            args["issue_description"],
                            args.get("job_type", "unknown")
                        )
                        _session_memory.update_lead_data(session_id, {"urgency_score": score})
                        extracted_lead["urgency_score"] = score

                elif fn_name == "update_conversation_state":
                    new_state = args.get("new_state")

        # Get text reply (may come with or without tool calls)
        if msg.content:
            reply_text = msg.content
        else:
            # Model made only tool calls — generate a follow-up reply
            # Re-call without tools to get the verbal response
            try:
                session_msgs = _session_memory.get_openai_messages(session_id)
                business = self._business
                system_prompt = build_system_prompt(
                    business_name=business.get("name", "Desert Air HVAC"),
                    booking_hours=business.get("booking_hours", "7am-7pm Mon-Sat"),
                    state=new_state or session["state"],
                    lead_data=_session_memory.get(session_id)["lead_data"]
                )
                follow_up = self._client.chat.completions.create(
                    model=config.OPENAI_CHAT_MODEL,
                    messages=[{"role": "system", "content": system_prompt}] + session_msgs,
                    temperature=0.7,
                    max_tokens=300,
                )
                reply_text = follow_up.choices[0].message.content or ""
            except Exception as e:
                logger.error("Follow-up completion error: %s", e)
                reply_text = self._fallback_response(new_state or session["state"])

        # Emergency escalation check
        urgency = _session_memory.get(session_id)["lead_data"].get("urgency_score", 0)
        if urgency >= 8 and session["state"] not in (State.EMERGENCY, State.BOOKING, State.CONFIRMATION):
            new_state = State.EMERGENCY

        return reply_text, extracted_lead, new_state

    def _upsert_lead(self, session_id: str, session: Dict, lead_data: Dict) -> Optional[int]:
        """Create or update the lead record in CRM."""
        lead_id = session.get("lead_id")
        phone = lead_data.get("phone")

        try:
            if not lead_id:
                # Check if we already have this phone number
                if phone:
                    existing = LeadCRM.get_by_phone(phone)
                    if existing:
                        lead_id = existing["id"]

            if lead_id:
                LeadCRM.update(lead_id, **{
                    k: v for k, v in lead_data.items()
                    if k in ("name","phone","email","address","zip","job_type",
                             "system_type","system_age","urgency_score","issue_description","notes")
                })
            else:
                # Create new lead
                new_lead = LeadCRM.create(
                    business_id=session.get("business_id", 1),
                    name=lead_data.get("name", ""),
                    phone=lead_data.get("phone", ""),
                    email=lead_data.get("email", ""),
                    address=lead_data.get("address", ""),
                    zip=lead_data.get("zip", ""),
                    job_type=lead_data.get("job_type", "unknown"),
                    system_type=lead_data.get("system_type", "unknown"),
                    system_age=lead_data.get("system_age"),
                    urgency_score=lead_data.get("urgency_score", 0),
                    issue_description=lead_data.get("issue_description", ""),
                    status="contacted",
                    source=session.get("source", "inbound_call"),
                )
                lead_id = new_lead["id"]

            _session_memory.update(session_id, lead_id=lead_id)
            ConversationCRM.link_lead(session_id, lead_id)

        except Exception as e:
            logger.error("Error upserting lead: %s", e)

        return lead_id

    def _schedule_missed_call_followup(self, lead_id: Optional[int], lead_data: Dict):
        """Schedule an automated missed-call SMS for a new missed caller."""
        if not lead_id:
            return
        try:
            from datetime import timedelta
            scheduled = (datetime.utcnow() +
                         timedelta(seconds=config.MISSED_CALL_DELAY_SECONDS)).isoformat()
            FollowUpCRM.enqueue(
                lead_id=lead_id,
                follow_up_type="missed_call",
                scheduled_at=scheduled,
                message_template=(
                    f"Hi {lead_data.get('name', 'there')}, sorry we missed your call! "
                    "This is Sonora with {{business_name}}. How can we help? "
                    "Reply here or call us back anytime."
                )
            )
        except Exception as e:
            logger.error("Error scheduling missed-call follow-up: %s", e)

    # ── Demo / Fallback Responses ──────────────────────────────────────────────

    def _demo_response(self, session_id: str, message: str, session: Dict) -> Tuple[str, Dict]:
        """Scripted demo responses when OpenAI is not configured."""
        state = session["state"]
        turn = session["turn_count"]

        if state == State.GREETING or turn == 1:
            _session_memory.update(session_id, state=State.QUALIFICATION)
            reply = (f"Hi, thanks for calling {self._business.get('name', 'Desert Air HVAC')}! "
                     "This is Sonora — I'm here to help get you taken care of today. "
                     "Can I start with your name and tell me what's going on with your system?")
        elif state == State.QUALIFICATION and turn <= 3:
            reply = ("Got it! And is this your home AC, heating system, or a heat pump? "
                     "Also, roughly how old is the system — do you know?")
        elif turn <= 5:
            _session_memory.update(session_id, state=State.BOOKING)
            reply = ("Perfect. I want to make sure we get someone out to you quickly. "
                     "We have availability tomorrow morning or this afternoon — "
                     "which works better for you?")
        else:
            _session_memory.update(session_id, state=State.CONFIRMATION)
            reply = ("You're all set! I've got you scheduled. Your tech will call when on the way. "
                     "Is there anything else I can help you with today?")

        ConversationCRM.append_message(session_id, "assistant", reply)
        return reply, {**session["lead_data"], "lead_id": session.get("lead_id"),
                       "state": _session_memory.get(session_id)["state"]}

    def _fallback_response(self, state: str) -> str:
        fallbacks = {
            State.GREETING:      "Hi there! This is Sonora — what's going on with your system today?",
            State.QUALIFICATION: "Got it! Can you tell me a bit more about what you're experiencing?",
            State.URGENCY_CHECK: "I understand — is the system completely out or still somewhat working?",
            State.EMERGENCY:     "I hear you — that needs immediate attention. What's your address so I can get someone to you right away?",
            State.BOOKING:       "Let me get you scheduled. Do you prefer mornings or afternoons?",
            State.CONFIRMATION:  "You're all set! Is there anything else I can help with?",
            State.FOLLOW_UP:     "How did everything go with the service?",
            State.REVIEW_REQUEST:"If you have a moment, we'd love a quick Google review — it helps families in your area find us!",
        }
        return fallbacks.get(state, "I'm here to help — what can I do for you today?")

    # ── Public Utilities ───────────────────────────────────────────────────────

    def get_greeting(self, business_name: Optional[str] = None) -> str:
        """Generate the opening greeting Sonora uses to answer a call."""
        name = business_name or self._business.get("name", "Desert Air HVAC")
        return (f"Hi, thanks for calling {name}! This is Sonora — "
                "I'm here to help get you taken care of today. "
                "Can I start with your name and tell me what's going on with your system?")

    def generate_missed_call_sms(self, lead_name: str, business_name: str) -> str:
        """Generate a missed-call recovery SMS text."""
        first = lead_name.split()[0] if lead_name else "there"
        return (f"Hi {first}, sorry we missed your call! This is Sonora with {business_name}. "
                f"How can we help? Reply here or call us back anytime.")

    def set_session_source(self, session_id: str, source: str):
        """Tag a session's lead source (inbound_call, missed_call, web_form, referral)."""
        _session_memory.update(session_id, source=source)

    def set_session_business(self, session_id: str, business_id: int):
        _session_memory.update(session_id, business_id=business_id)

    def get_session(self, session_id: str) -> Dict:
        return _session_memory.get(session_id)

    def reset_session(self, session_id: str):
        _session_memory.clear(session_id)
