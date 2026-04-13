"""
seed_data.py — Sonora HVAC Demo Data Seeder

Seeds the database with:
  - 1 demo HVAC business (Desert Air HVAC — Phoenix, AZ)
  - 15 realistic HVAC leads across all statuses and job types
  - 8 appointments (upcoming and completed)
  - Sample conversations showing Sonora qualifying leads
  - Follow-up queue with pending tasks
  - Review requests

Revenue estimates:
  - Service call: $150
  - Repair (capacitor, refrigerant, etc.): $150-600
  - Install (new system): $3,500-7,500
  - Maintenance: $89-149

Run: python seed_data.py
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config import config
from sonora.crm import init_db

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def dt(days_offset: int = 0, hours: int = 9) -> str:
    """Return an ISO datetime string offset from now."""
    return (datetime.utcnow() + timedelta(days=days_offset)).replace(
        hour=hours, minute=0, second=0, microsecond=0
    ).isoformat()


def past(days: int = 1, hours: int = 10) -> str:
    return dt(-days, hours)


def future(days: int = 1, hours: int = 10) -> str:
    return dt(days, hours)


def now() -> str:
    return datetime.utcnow().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Seed Function
# ─────────────────────────────────────────────────────────────────────────────

def seed():
    print("🌵 Seeding Sonora HVAC demo database...")
    init_db()

    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # ── 1. Business ────────────────────────────────────────────────────────────
    print("  → Seeding business...")

    # Clear existing data (clean slate)
    for table in ["reviews", "follow_up_queue", "conversations", "appointments",
                   "leads", "businesses"]:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('reviews','follow_up_queue','conversations','appointments','leads','businesses')")
    conn.commit()

    conn.execute("""
        INSERT INTO businesses (id, name, phone, service_area, booking_hours,
                                avg_ticket_repair, avg_ticket_install)
        VALUES (1, 'Desert Air HVAC', '+16025551234',
                'Phoenix, Scottsdale, Tempe, Mesa, Chandler, Gilbert AZ',
                '7am-7pm Mon-Sat', 285.0, 5200.0)
    """)
    conn.commit()

    # ── 2. Leads (15 realistic HVAC leads) ────────────────────────────────────
    print("  → Seeding 15 leads...")

    leads = [
        # 1. Emergency — no AC in Phoenix summer heat (urgency 10)
        {
            "id": 1, "business_id": 1,
            "name": "Maria Gonzalez", "phone": "+16025551001",
            "email": "maria.g@email.com",
            "address": "4521 E Camelback Rd", "zip": "85018",
            "job_type": "emergency", "system_type": "ac",
            "system_age": 12, "urgency_score": 10,
            "issue_description": "AC is completely out, not turning on at all. It's 108 degrees and we have a baby in the house.",
            "status": "booked", "source": "inbound_call",
            "notes": "PRIORITY — baby in home. Customer is very stressed.",
            "created_at": past(0, 8), "updated_at": past(0, 8),
        },
        # 2. Repair — heat pump blowing warm air (urgency 7)
        {
            "id": 2, "business_id": 1,
            "name": "James Whitfield", "phone": "+16025551002",
            "email": "jwhitfield@gmail.com",
            "address": "789 W Indian School Rd", "zip": "85013",
            "job_type": "repair", "system_type": "heat_pump",
            "system_age": 8, "urgency_score": 7,
            "issue_description": "Heat pump running all day but blowing warm air, not cooling. System is 8 years old.",
            "status": "booked", "source": "inbound_call",
            "notes": "Likely refrigerant leak or capacitor issue.",
            "created_at": past(1, 9), "updated_at": past(1, 9),
        },
        # 3. Install — full system replacement (urgency 5)
        {
            "id": 3, "business_id": 1,
            "name": "Sandra Kim", "phone": "+16025551003",
            "email": "sandrak@yahoo.com",
            "address": "12 N Scottsdale Rd", "zip": "85251",
            "job_type": "install", "system_type": "ac",
            "system_age": 22, "urgency_score": 5,
            "issue_description": "22-year-old Carrier unit. Getting quotes for full replacement — central AC and air handler.",
            "status": "qualified", "source": "web_form",
            "notes": "Homeowner, interested in Trane or Carrier 2-stage. Has financing questions.",
            "created_at": past(3, 11), "updated_at": past(2, 14),
        },
        # 4. Maintenance — annual tune-up (urgency 2)
        {
            "id": 4, "business_id": 1,
            "name": "Robert Delgado", "phone": "+16025551004",
            "email": "rdelgado@outlook.com",
            "address": "5500 S Rural Rd", "zip": "85283",
            "job_type": "maintenance", "system_type": "ac",
            "system_age": 6, "urgency_score": 2,
            "issue_description": "Annual AC tune-up before summer. Also want to check refrigerant levels.",
            "status": "booked", "source": "referral",
            "notes": "Referred by Maria Gonzalez (lead #1). Prefers morning appointments.",
            "created_at": past(5, 10), "updated_at": past(4, 9),
        },
        # 5. Emergency — CO detector alarm (urgency 10)
        {
            "id": 5, "business_id": 1,
            "name": "Thomas Hart", "phone": "+16025551005",
            "email": "",
            "address": "3322 W Thunderbird Rd", "zip": "85053",
            "job_type": "emergency", "system_type": "heat",
            "system_age": 15, "urgency_score": 10,
            "issue_description": "Carbon monoxide alarm going off near the furnace. Family evacuated. Need someone NOW.",
            "status": "completed", "source": "inbound_call",
            "notes": "EMERGENCY handled same day. Cracked heat exchanger found. Furnace condemned. Referred to install team.",
            "created_at": past(14, 7), "updated_at": past(14, 16),
        },
        # 6. Repair — capacitor replacement (urgency 6)
        {
            "id": 6, "business_id": 1,
            "name": "Angela Torres", "phone": "+16025551006",
            "email": "angela.torres@hotmail.com",
            "address": "8811 E McDowell Rd", "zip": "85257",
            "job_type": "repair", "system_type": "ac",
            "system_age": 11, "urgency_score": 6,
            "issue_description": "AC makes a clicking noise then stops. Runs for a few minutes, shuts off. Breaker trips.",
            "status": "completed", "source": "missed_call",
            "notes": "Missed call recovery successful. Capacitor replaced on-site. Customer very happy.",
            "created_at": past(7, 14), "updated_at": past(6, 11),
        },
        # 7. Install — new build (urgency 3)
        {
            "id": 7, "business_id": 1,
            "name": "David Park", "phone": "+16025551007",
            "email": "dpark@gmail.com",
            "address": "221 N Gilbert Rd", "zip": "85234",
            "job_type": "install", "system_type": "both",
            "system_age": 0, "urgency_score": 3,
            "issue_description": "New construction — need full HVAC system installed. Builder spec calls for 3.5-ton split system.",
            "status": "qualified", "source": "referral",
            "notes": "Builder referral from Sunbelt Construction. Multiple units — potential large contract.",
            "created_at": past(10, 9), "updated_at": past(8, 15),
        },
        # 8. Repair — strange smell (urgency 5)
        {
            "id": 8, "business_id": 1,
            "name": "Lisa Nguyen", "phone": "+16025551008",
            "email": "lisanguyen@icloud.com",
            "address": "417 E Chandler Blvd", "zip": "85225",
            "job_type": "repair", "system_type": "ac",
            "system_age": 9, "urgency_score": 5,
            "issue_description": "Burning smell coming from vents when AC turns on. Has been going on 2 days.",
            "status": "new", "source": "inbound_call",
            "notes": "Scheduled callback for tomorrow 10am.",
            "created_at": past(0, 16), "updated_at": past(0, 16),
        },
        # 9. Maintenance — seasonal prep (urgency 2)
        {
            "id": 9, "business_id": 1,
            "name": "William Chen", "phone": "+16025551009",
            "email": "wchen@protonmail.com",
            "address": "5650 W Bell Rd", "zip": "85308",
            "job_type": "maintenance", "system_type": "both",
            "system_age": 4, "urgency_score": 2,
            "issue_description": "Pre-summer AC tune-up on both units. Also want duct inspection.",
            "status": "booked", "source": "web_form",
            "notes": "Two-unit home. Requested same tech as last year.",
            "created_at": past(4, 8), "updated_at": past(3, 10),
        },
        # 10. Missed call — no AC (urgency 8)
        {
            "id": 10, "business_id": 1,
            "name": "Patricia Moore", "phone": "+16025551010",
            "email": "",
            "address": "", "zip": "85040",
            "job_type": "repair", "system_type": "ac",
            "system_age": None, "urgency_score": 8,
            "issue_description": "No cooling at all. Left a voicemail — Sonora sent recovery SMS.",
            "status": "contacted", "source": "missed_call",
            "notes": "Sonora SMS sent 2 minutes after missed call. Awaiting reply.",
            "created_at": past(0, 11), "updated_at": past(0, 11),
        },
        # 11. Install — heat pump upgrade (urgency 4)
        {
            "id": 11, "business_id": 1,
            "name": "Kevin Johnson", "phone": "+16025551011",
            "email": "kjohnson@gmail.com",
            "address": "7800 E Shea Blvd", "zip": "85260",
            "job_type": "install", "system_type": "heat_pump",
            "system_age": 18, "urgency_score": 4,
            "issue_description": "Old R22 system — want to upgrade to a heat pump. Got a competitor quote of $6,800.",
            "status": "lost", "source": "inbound_call",
            "notes": "Lost to competitor on price. Reactivation candidate in fall.",
            "created_at": past(45, 10), "updated_at": past(40, 9),
        },
        # 12. Repair — high electric bill (urgency 4)
        {
            "id": 12, "business_id": 1,
            "name": "Rachel Stevens", "phone": "+16025551012",
            "email": "rachel.s@yahoo.com",
            "address": "3310 E Baseline Rd", "zip": "85204",
            "job_type": "repair", "system_type": "ac",
            "system_age": 7, "urgency_score": 4,
            "issue_description": "Electric bill jumped $180 last month. AC running constantly but house not cool.",
            "status": "qualified", "source": "web_form",
            "notes": "Likely dirty coils or refrigerant issue. Follow up scheduled.",
            "created_at": past(2, 13), "updated_at": past(1, 14),
        },
        # 13. Emergency — no heat in winter (urgency 9) — historical
        {
            "id": 13, "business_id": 1,
            "name": "Carlos Rivera", "phone": "+16025551013",
            "email": "crivera@gmail.com",
            "address": "924 W Glendale Ave", "zip": "85301",
            "job_type": "emergency", "system_type": "heat",
            "system_age": 13, "urgency_score": 9,
            "issue_description": "No heat. Outside is 38 degrees. Elderly parent in the house.",
            "status": "completed", "source": "inbound_call",
            "notes": "Ignitor replacement. Same-day service. Customer left 5-star Google review.",
            "created_at": past(90, 8), "updated_at": past(90, 15),
        },
        # 14. New lead — just called (urgency 0)
        {
            "id": 14, "business_id": 1,
            "name": "", "phone": "+16025551014",
            "email": "",
            "address": "", "zip": "",
            "job_type": "unknown", "system_type": "unknown",
            "system_age": None, "urgency_score": 0,
            "issue_description": "Inbound call — Sonora is currently qualifying.",
            "status": "new", "source": "inbound_call",
            "notes": "Active session in progress.",
            "created_at": now(), "updated_at": now(),
        },
        # 15. Referral — maintenance plan inquiry (urgency 1)
        {
            "id": 15, "business_id": 1,
            "name": "Donna Walsh", "phone": "+16025551015",
            "email": "donna.walsh@gmail.com",
            "address": "609 S Higley Rd", "zip": "85206",
            "job_type": "maintenance", "system_type": "ac",
            "system_age": 5, "urgency_score": 1,
            "issue_description": "Neighbor recommended Desert Air. Interested in annual maintenance plan pricing.",
            "status": "contacted", "source": "referral",
            "notes": "Interested in a 2-visit yearly plan. Follow up with pricing sheet.",
            "created_at": past(1, 16), "updated_at": past(1, 16),
        },
    ]

    for lead in leads:
        conn.execute("""
            INSERT INTO leads (id, business_id, name, phone, email, address, zip,
                job_type, system_type, system_age, urgency_score, issue_description,
                status, source, notes, created_at, updated_at)
            VALUES (:id, :business_id, :name, :phone, :email, :address, :zip,
                :job_type, :system_type, :system_age, :urgency_score, :issue_description,
                :status, :source, :notes, :created_at, :updated_at)
        """, lead)
    conn.commit()

    # ── 3. Appointments (8 realistic appointments) ─────────────────────────────
    print("  → Seeding 8 appointments...")

    appointments = [
        # Upcoming
        {
            "id": 1, "lead_id": 1,
            "scheduled_at": future(0, 10),  # Today at 10am
            "job_type": "emergency",
            "tech_assigned": "Mike Reyes",
            "duration_hours": 3.0, "status": "confirmed",
            "revenue_estimate": 450.0,
            "notes": "Emergency AC repair. Bring extra capacitors. Customer has baby.",
            "created_at": past(0, 8), "updated_at": past(0, 8),
        },
        {
            "id": 2, "lead_id": 2,
            "scheduled_at": future(1, 9),  # Tomorrow 9am
            "job_type": "repair",
            "tech_assigned": "Jason T.",
            "duration_hours": 2.0, "status": "scheduled",
            "revenue_estimate": 350.0,
            "notes": "Heat pump repair — check refrigerant and capacitor.",
            "created_at": past(1, 9), "updated_at": past(1, 9),
        },
        {
            "id": 3, "lead_id": 4,
            "scheduled_at": future(2, 8),  # In 2 days at 8am
            "job_type": "maintenance",
            "tech_assigned": "Mike Reyes",
            "duration_hours": 1.5, "status": "scheduled",
            "revenue_estimate": 129.0,
            "notes": "Annual tune-up. Check refrigerant, clean coils, replace filter.",
            "created_at": past(5, 10), "updated_at": past(5, 10),
        },
        {
            "id": 4, "lead_id": 9,
            "scheduled_at": future(3, 14),  # 3 days out, 2pm
            "job_type": "maintenance",
            "tech_assigned": "Sarah L.",
            "duration_hours": 3.0, "status": "scheduled",
            "revenue_estimate": 258.0,  # Two units
            "notes": "Two-unit home. Both units need tune-up + duct check.",
            "created_at": past(4, 8), "updated_at": past(3, 10),
        },
        # Completed historical
        {
            "id": 5, "lead_id": 6,
            "scheduled_at": past(6, 10),
            "job_type": "repair",
            "tech_assigned": "Jason T.",
            "duration_hours": 1.5, "status": "completed",
            "revenue_estimate": 285.0,
            "notes": "Capacitor replaced. System running perfectly. Customer happy.",
            "created_at": past(7, 14), "updated_at": past(6, 12),
        },
        {
            "id": 6, "lead_id": 5,
            "scheduled_at": past(14, 9),
            "job_type": "emergency",
            "tech_assigned": "Mike Reyes",
            "duration_hours": 2.0, "status": "completed",
            "revenue_estimate": 150.0,  # Service call only — unit condemned
            "notes": "Cracked heat exchanger. Carbon monoxide risk. Furnace condemned. Install quote given.",
            "created_at": past(14, 7), "updated_at": past(14, 17),
        },
        {
            "id": 7, "lead_id": 13,
            "scheduled_at": past(90, 9),
            "job_type": "emergency",
            "tech_assigned": "Dave K.",
            "duration_hours": 2.0, "status": "completed",
            "revenue_estimate": 320.0,
            "notes": "Ignitor + heat sensor replacement. Heating restored same day.",
            "created_at": past(90, 8), "updated_at": past(90, 16),
        },
        {
            "id": 8, "lead_id": 3,
            "scheduled_at": future(7, 10),  # Estimate appointment next week
            "job_type": "install",
            "tech_assigned": "Sarah L.",
            "duration_hours": 1.0, "status": "scheduled",
            "revenue_estimate": 5200.0,  # Full system install estimate
            "notes": "Site visit + estimate for full system replacement. Bring Trane/Carrier spec sheets.",
            "created_at": past(3, 11), "updated_at": past(2, 14),
        },
    ]

    for appt in appointments:
        conn.execute("""
            INSERT INTO appointments (id, lead_id, scheduled_at, job_type, tech_assigned,
                duration_hours, status, revenue_estimate, notes, created_at, updated_at)
            VALUES (:id, :lead_id, :scheduled_at, :job_type, :tech_assigned,
                :duration_hours, :status, :revenue_estimate, :notes, :created_at, :updated_at)
        """, appt)
    conn.commit()

    # ── 4. Sample Conversations ────────────────────────────────────────────────
    print("  → Seeding sample conversations...")

    conversations = [
        # Emergency call — Sonora qualifying Maria
        {
            "session_id": "sess_emergency_001",
            "lead_id": 1,
            "messages": json.dumps([
                {"role": "assistant", "content": "Hi, thanks for calling Desert Air HVAC! This is Sonora — I'm here to help get you taken care of today. Can I start with your name and tell me what's going on with your system?", "timestamp": past(0, 8)},
                {"role": "user",      "content": "Hi yes — my name is Maria Gonzalez, and my AC just completely stopped working. It won't turn on at all. It's 108 degrees and I have a 6-month-old baby!", "timestamp": past(0, 8)},
                {"role": "assistant", "content": "Maria — I hear you, and I want you to know we are going to get someone to you as fast as possible. No AC in this heat with a baby is an emergency and we're treating it as one. Can you give me your address right now so I can get a tech dispatched?", "timestamp": past(0, 8)},
                {"role": "user",      "content": "Yes! 4521 East Camelback Road, Phoenix, 85018.", "timestamp": past(0, 8)},
                {"role": "assistant", "content": "Perfect. I've got you at 4521 E Camelback Rd. Our tech Mike Reyes is in your area — he can be there by 10am today, possibly sooner. Is that okay? And is your system central AC, about how old?", "timestamp": past(0, 8)},
                {"role": "user",      "content": "Yes 10am is fine, it's a central AC unit, probably 12 years old. Carrier brand I think.", "timestamp": past(0, 8)},
                {"role": "assistant", "content": "You're all set, Maria. Mike Reyes will be there at 10am and will call you when he's 20 minutes out. Keep the baby cool with fans and any battery-powered options in the meantime. We'll get you back up and running — I promise. Is there anything else you need right now?", "timestamp": past(0, 8)},
                {"role": "user",      "content": "No that's perfect, thank you so much!", "timestamp": past(0, 8)},
            ]),
            "created_at": past(0, 8), "updated_at": past(0, 8),
        },
        # Missed call recovery — Angela Torres
        {
            "session_id": "sess_missedcall_006",
            "lead_id": 6,
            "messages": json.dumps([
                {"role": "assistant", "content": "Hi Angela, sorry we missed your call! This is Sonora with Desert Air HVAC. How can we help? Reply here or call us back anytime.", "timestamp": past(7, 14)},
                {"role": "user",      "content": "Hi! My AC keeps making a clicking noise and then shutting off. The breaker tripped twice already.", "timestamp": past(7, 15)},
                {"role": "assistant", "content": "Angela, that clicking + breaker tripping is a red flag — sounds like it could be a bad capacitor or the compressor is struggling. The good news is this is usually a quick fix. What's your address so I can get a tech out to you?", "timestamp": past(7, 15)},
                {"role": "user",      "content": "8811 E McDowell Road, Scottsdale 85257.", "timestamp": past(7, 15)},
                {"role": "assistant", "content": "Perfect. I can get Jason T. out to you tomorrow morning between 8-10am. He'll diagnose it and have it fixed in one visit in most cases. Does that work for you?", "timestamp": past(7, 15)},
                {"role": "user",      "content": "Yes tomorrow works great!", "timestamp": past(7, 15)},
                {"role": "assistant", "content": "You're scheduled! Jason will call you when he's on the way. Thanks for texting back, Angela — we've got you covered. ☀️", "timestamp": past(7, 15)},
            ]),
            "created_at": past(7, 14), "updated_at": past(7, 15),
        },
        # Web form lead — Sandra Kim (install)
        {
            "session_id": "sess_webform_003",
            "lead_id": 3,
            "messages": json.dumps([
                {"role": "assistant", "content": "Hi Sandra! This is Sonora with Desert Air HVAC — I saw your inquiry about replacing your AC system. Sounds like you've got a 22-year-old unit? That's definitely at end of life. Can I ask a few quick questions to get you the right quote?", "timestamp": past(3, 11)},
                {"role": "user",      "content": "Yes please! It's a Carrier unit, been having issues for 2 summers now. Just done.", "timestamp": past(3, 11)},
                {"role": "assistant", "content": "Totally understand — two problematic summers is more than enough. For a replacement, we'll want to know your home's square footage to right-size the system. Roughly how big is your home?", "timestamp": past(3, 11)},
                {"role": "user",      "content": "It's about 2,200 square feet, single story.", "timestamp": past(3, 11)},
                {"role": "assistant", "content": "Perfect — for 2,200 sq ft in Phoenix, you're typically looking at a 3.5-ton system. We typically install Trane or Carrier 2-stage units for great efficiency. Would you like to schedule a free on-site estimate? Our install specialist Sarah can come by, walk through the options, and give you an exact price.", "timestamp": past(3, 11)},
                {"role": "user",      "content": "Yes that would be great! Do you offer financing?", "timestamp": past(3, 11)},
                {"role": "assistant", "content": "We do! We work with GreenSky and Wells Fargo Home Projects — 12 and 18-month same-as-cash options. Sarah will go over all of it when she comes out. What day works for you next week for a 1-hour estimate visit?", "timestamp": past(3, 11)},
            ]),
            "created_at": past(3, 11), "updated_at": past(2, 14),
        },
    ]

    for conv in conversations:
        conn.execute("""
            INSERT INTO conversations (session_id, lead_id, messages, created_at, updated_at)
            VALUES (:session_id, :lead_id, :messages, :created_at, :updated_at)
        """, conv)
    conn.commit()

    # ── 5. Follow-Up Queue ─────────────────────────────────────────────────────
    print("  → Seeding follow-up queue...")

    follow_ups = [
        # Pending — appointment reminders
        {
            "lead_id": 2,
            "follow_up_type": "appt_reminder_24h",
            "scheduled_at": future(1, 9),  # Tomorrow before appointment
            "status": "pending",
            "message_template": "Hi James, heads up — your heat pump repair appointment is tomorrow at 9am. Jason T. will call when on the way. Reply CONFIRM or RESCHEDULE if needed.",
            "created_at": now(),
        },
        {
            "lead_id": 4,
            "follow_up_type": "appt_reminder_24h",
            "scheduled_at": future(2, 7),
            "status": "pending",
            "message_template": "Hi Robert, reminder — your annual AC tune-up is tomorrow at 8am with Mike Reyes. Please make sure someone 18+ is home. See you soon!",
            "created_at": now(),
        },
        # Missed call nurture sequence — Patricia Moore
        {
            "lead_id": 10,
            "follow_up_type": "missed_call",
            "scheduled_at": past(0, 11),  # Already due
            "status": "sent",
            "message_template": "Hi Patricia, sorry we missed your call! This is Sonora with Desert Air HVAC. We'd love to help with your AC. Reply here or call us back anytime!",
            "sent_at": past(0, 11),
            "created_at": past(0, 11),
        },
        {
            "lead_id": 10,
            "follow_up_type": "nurture_24h",
            "scheduled_at": future(1, 11),
            "status": "pending",
            "message_template": "Hi Patricia, this is Sonora with Desert Air HVAC. Still thinking about your AC? We still have openings this week and would love to help. Reply to get scheduled!",
            "created_at": past(0, 11),
        },
        {
            "lead_id": 10,
            "follow_up_type": "nurture_3d",
            "scheduled_at": future(3, 11),
            "status": "pending",
            "message_template": "Hey Patricia! Sonora here. Our techs are in your area this week — let's get your AC sorted before the heat picks up more. Reply here to schedule!",
            "created_at": past(0, 11),
        },
        # Donna Walsh — nurture follow-up
        {
            "lead_id": 15,
            "follow_up_type": "nurture_24h",
            "scheduled_at": future(1, 16),
            "status": "pending",
            "message_template": "Hi Donna! This is Sonora with Desert Air HVAC. Just following up on your maintenance plan inquiry. Our most popular plan is 2 visits/year at $199 — covers both heating and cooling seasons. Want me to get you set up?",
            "created_at": past(1, 16),
        },
        # Post-job review — Carlos Rivera (historical)
        {
            "lead_id": 13,
            "follow_up_type": "post_job_review",
            "scheduled_at": past(89, 19),
            "status": "sent",
            "message_template": "Hi Carlos, it was great taking care of your heating today! If everything is running great, would you mind leaving us a quick Google review? It takes 60 seconds and means the world to our team!",
            "sent_at": past(89, 19),
            "created_at": past(90, 17),
        },
        # Seasonal reactivation — Kevin Johnson (lost lead)
        {
            "lead_id": 11,
            "follow_up_type": "seasonal_reactivation",
            "scheduled_at": future(5, 10),
            "status": "pending",
            "message_template": "Hi Kevin! With summer coming, now's the perfect time for a tune-up — or to revisit that heat pump upgrade. We have new financing options and may be able to beat that competitor quote. Interested? — Sonora, Desert Air HVAC",
            "created_at": now(),
        },
    ]

    for fu in follow_ups:
        conn.execute("""
            INSERT INTO follow_up_queue (lead_id, follow_up_type, scheduled_at, status,
                message_template, sent_at, created_at)
            VALUES (:lead_id, :follow_up_type, :scheduled_at, :status,
                :message_template, :sent_at, :created_at)
        """, {**fu, "sent_at": fu.get("sent_at")})
    conn.commit()

    # ── 6. Review Requests ─────────────────────────────────────────────────────
    print("  → Seeding review requests...")

    reviews = [
        {
            "lead_id": 6, "appointment_id": 5,
            "requested_at": past(6, 14),
            "platform": "google", "status": "completed",
            "message_sent": "Hi Angela, so glad we could fix your AC today! Would you mind leaving us a quick Google review? Every review helps us help more families in Phoenix. Thank you! — Sonora",
        },
        {
            "lead_id": 13, "appointment_id": 7,
            "requested_at": past(89, 19),
            "platform": "google", "status": "completed",
            "message_sent": "Hi Carlos, it was great taking care of your heating today! If everything is running great, we'd love a quick Google review. It helps families in Glendale find us when they need help most!",
        },
        {
            "lead_id": 5, "appointment_id": 6,
            "requested_at": past(14, 20),
            "platform": "google", "status": "sent",
            "message_sent": "Hi Thomas, we're so glad your family is safe. If you have a moment, a Google review would mean the world to our small team — it helps other Phoenix families find us in emergencies.",
        },
        {
            "lead_id": 1, "appointment_id": 1,
            "requested_at": None,
            "platform": "google", "status": "pending",
            "message_sent": None,
        },
    ]

    for review in reviews:
        conn.execute("""
            INSERT INTO reviews (lead_id, appointment_id, requested_at, platform, status, message_sent)
            VALUES (:lead_id, :appointment_id, :requested_at, :platform, :status, :message_sent)
        """, review)
    conn.commit()

    conn.close()

    print("\n✅ Seed complete! Database: %s" % config.DATABASE_PATH)
    print("\nSummary:")
    print("  • 1 business  : Desert Air HVAC — Phoenix, AZ")
    print("  • 15 leads    : Across all statuses and job types")
    print("  • 8 appts     : 4 upcoming, 3 completed, 1 estimate")
    print("  • 3 convos    : Sonora qualifying leads in action")
    print("  • 8 follow-ups: Pending, sent, and scheduled")
    print("  • 4 reviews   : Google review request queue")
    print("\nPipeline revenue estimate: $5,200 (install) + $1,337 (service)")
    print("Total pipeline: ~$6,537\n")


if __name__ == "__main__":
    seed()
