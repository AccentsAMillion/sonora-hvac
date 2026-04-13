"""
sonora/crm.py — Sonora HVAC CRM
SQLite-backed data layer for leads, appointments, conversations, businesses,
follow-up queue, and review requests.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from config import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Schema DDL
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
-- Businesses registered with Sonora
CREATE TABLE IF NOT EXISTS businesses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT,
    service_area    TEXT,
    booking_hours   TEXT DEFAULT '7am-7pm Mon-Sat',
    avg_ticket_repair   REAL DEFAULT 150.0,
    avg_ticket_install  REAL DEFAULT 4500.0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leads (potential customers)
CREATE TABLE IF NOT EXISTS leads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id         INTEGER REFERENCES businesses(id),
    name                TEXT,
    phone               TEXT,
    email               TEXT,
    address             TEXT,
    zip                 TEXT,
    job_type            TEXT CHECK(job_type IN ('repair','install','maintenance','emergency','unknown')) DEFAULT 'unknown',
    system_type         TEXT CHECK(system_type IN ('ac','heat','heat_pump','both','unknown')) DEFAULT 'unknown',
    system_age          INTEGER,
    urgency_score       INTEGER DEFAULT 0 CHECK(urgency_score BETWEEN 0 AND 10),
    issue_description   TEXT,
    status              TEXT CHECK(status IN ('new','contacted','qualified','booked','completed','lost')) DEFAULT 'new',
    source              TEXT CHECK(source IN ('inbound_call','missed_call','web_form','referral')) DEFAULT 'inbound_call',
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER REFERENCES leads(id),
    scheduled_at    TIMESTAMP,
    job_type        TEXT,
    tech_assigned   TEXT,
    duration_hours  REAL DEFAULT 2.0,
    status          TEXT CHECK(status IN ('scheduled','confirmed','in_progress','completed','cancelled','no_show')) DEFAULT 'scheduled',
    revenue_estimate REAL DEFAULT 0.0,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation logs (session → messages JSON)
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    lead_id     INTEGER REFERENCES leads(id),
    messages    TEXT DEFAULT '[]',   -- JSON array of {role, content, timestamp}
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);

-- Automated follow-up queue
CREATE TABLE IF NOT EXISTS follow_up_queue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id             INTEGER REFERENCES leads(id),
    follow_up_type      TEXT CHECK(follow_up_type IN (
                            'missed_call','nurture_24h','nurture_3d','nurture_7d',
                            'appt_reminder_24h','appt_reminder_2h',
                            'post_job_review','seasonal_reactivation'
                        )) NOT NULL,
    scheduled_at        TIMESTAMP NOT NULL,
    status              TEXT CHECK(status IN ('pending','sent','failed','skipped')) DEFAULT 'pending',
    message_template    TEXT,
    sent_at             TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_followup_status ON follow_up_queue(status, scheduled_at);

-- Review requests
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER REFERENCES leads(id),
    appointment_id  INTEGER REFERENCES appointments(id),
    requested_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    platform        TEXT CHECK(platform IN ('google','yelp')) DEFAULT 'google',
    status          TEXT CHECK(status IN ('pending','sent','clicked','completed','declined')) DEFAULT 'pending',
    message_sent    TEXT
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection with row_factory set."""
    conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize all tables."""
    with db_conn() as conn:
        conn.executescript(SCHEMA)
    logger.info("Sonora CRM database initialized at %s", config.DATABASE_PATH)


def row_to_dict(row) -> Optional[Dict]:
    if row is None:
        return None
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Businesses
# ─────────────────────────────────────────────────────────────────────────────

class BusinessCRM:
    @staticmethod
    def create(name: str, phone: str = "", service_area: str = "",
               booking_hours: str = "7am-7pm Mon-Sat",
               avg_ticket_repair: float = 150.0,
               avg_ticket_install: float = 4500.0) -> Dict:
        with db_conn() as conn:
            cur = conn.execute(
                """INSERT INTO businesses (name, phone, service_area, booking_hours,
                   avg_ticket_repair, avg_ticket_install)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, phone, service_area, booking_hours, avg_ticket_repair, avg_ticket_install)
            )
            return {"id": cur.lastrowid, "name": name}

    @staticmethod
    def get(business_id: int) -> Optional[Dict]:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM businesses WHERE id=?", (business_id,)
            ).fetchone()
            return row_to_dict(row)

    @staticmethod
    def get_all() -> List[Dict]:
        with db_conn() as conn:
            rows = conn.execute("SELECT * FROM businesses ORDER BY id").fetchall()
            return [row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────────────────────────────────────

class LeadCRM:
    @staticmethod
    def create(business_id: int = 1,
               name: str = "", phone: str = "", email: str = "",
               address: str = "", zip: str = "",
               job_type: str = "unknown", system_type: str = "unknown",
               system_age: Optional[int] = None,
               urgency_score: int = 0, issue_description: str = "",
               status: str = "new", source: str = "inbound_call",
               notes: str = "") -> Dict:
        now = datetime.utcnow().isoformat()
        with db_conn() as conn:
            cur = conn.execute(
                """INSERT INTO leads (business_id, name, phone, email, address, zip,
                   job_type, system_type, system_age, urgency_score, issue_description,
                   status, source, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (business_id, name, phone, email, address, zip,
                 job_type, system_type, system_age, urgency_score, issue_description,
                 status, source, notes, now, now)
            )
            lead_id = cur.lastrowid
        return LeadCRM.get(lead_id)

    @staticmethod
    def get(lead_id: int) -> Optional[Dict]:
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            return row_to_dict(row)

    @staticmethod
    def get_all(business_id: Optional[int] = None,
                status: Optional[str] = None,
                source: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        if business_id:
            query += " AND business_id=?"
            params.append(business_id)
        if status:
            query += " AND status=?"
            params.append(status)
        if source:
            query += " AND source=?"
            params.append(source)
        query += " ORDER BY created_at DESC"
        with db_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [row_to_dict(r) for r in rows]

    @staticmethod
    def update(lead_id: int, **fields) -> Optional[Dict]:
        allowed = {
            "name","phone","email","address","zip","job_type","system_type",
            "system_age","urgency_score","issue_description","status","source","notes"
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return LeadCRM.get(lead_id)
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [lead_id]
        with db_conn() as conn:
            conn.execute(f"UPDATE leads SET {set_clause} WHERE id=?", values)
        return LeadCRM.get(lead_id)

    @staticmethod
    def get_by_phone(phone: str) -> Optional[Dict]:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM leads WHERE phone=? ORDER BY created_at DESC LIMIT 1",
                (phone,)
            ).fetchone()
            return row_to_dict(row)

    @staticmethod
    def count_today(business_id: int = 1) -> int:
        today = datetime.utcnow().date().isoformat()
        with db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM leads WHERE business_id=? AND DATE(created_at)=?",
                (business_id, today)
            ).fetchone()
            return row["n"] if row else 0

    @staticmethod
    def get_dormant(business_id: int = 1, days: int = 90) -> List[Dict]:
        """Leads inactive for `days` days — for seasonal reactivation campaigns."""
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM leads
                   WHERE business_id=?
                   AND status IN ('completed','lost')
                   AND DATE(updated_at) <= DATE('now', ?)
                   ORDER BY updated_at ASC""",
                (business_id, f"-{days} days")
            ).fetchall()
            return [row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Appointments
# ─────────────────────────────────────────────────────────────────────────────

class AppointmentCRM:
    @staticmethod
    def create(lead_id: int, scheduled_at: str, job_type: str = "",
               tech_assigned: str = "", duration_hours: float = 2.0,
               revenue_estimate: float = 0.0, notes: str = "") -> Dict:
        now = datetime.utcnow().isoformat()
        with db_conn() as conn:
            cur = conn.execute(
                """INSERT INTO appointments (lead_id, scheduled_at, job_type, tech_assigned,
                   duration_hours, revenue_estimate, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (lead_id, scheduled_at, job_type, tech_assigned,
                 duration_hours, revenue_estimate, notes, now, now)
            )
            appt_id = cur.lastrowid
        # Update lead status to booked
        LeadCRM.update(lead_id, status="booked")
        return AppointmentCRM.get(appt_id)

    @staticmethod
    def get(appt_id: int) -> Optional[Dict]:
        with db_conn() as conn:
            row = conn.execute(
                """SELECT a.*, l.name as lead_name, l.phone as lead_phone
                   FROM appointments a LEFT JOIN leads l ON a.lead_id=l.id
                   WHERE a.id=?""",
                (appt_id,)
            ).fetchone()
            return row_to_dict(row)

    @staticmethod
    def get_all(lead_id: Optional[int] = None,
                status: Optional[str] = None) -> List[Dict]:
        query = """SELECT a.*, l.name as lead_name, l.phone as lead_phone
                   FROM appointments a LEFT JOIN leads l ON a.lead_id=l.id
                   WHERE 1=1"""
        params = []
        if lead_id:
            query += " AND a.lead_id=?"
            params.append(lead_id)
        if status:
            query += " AND a.status=?"
            params.append(status)
        query += " ORDER BY a.scheduled_at ASC"
        with db_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [row_to_dict(r) for r in rows]

    @staticmethod
    def update(appt_id: int, **fields) -> Optional[Dict]:
        allowed = {
            "scheduled_at","job_type","tech_assigned","duration_hours",
            "status","revenue_estimate","notes"
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return AppointmentCRM.get(appt_id)
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [appt_id]
        with db_conn() as conn:
            conn.execute(f"UPDATE appointments SET {set_clause} WHERE id=?", values)
        return AppointmentCRM.get(appt_id)

    @staticmethod
    def count_booked(business_id: int = 1) -> int:
        with db_conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as n FROM appointments a
                   JOIN leads l ON a.lead_id=l.id
                   WHERE l.business_id=? AND a.status IN ('scheduled','confirmed','completed')""",
                (business_id,)
            ).fetchone()
            return row["n"] if row else 0

    @staticmethod
    def total_revenue_estimate(business_id: int = 1) -> float:
        with db_conn() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(a.revenue_estimate),0) as total FROM appointments a
                   JOIN leads l ON a.lead_id=l.id
                   WHERE l.business_id=? AND a.status NOT IN ('cancelled','no_show')""",
                (business_id,)
            ).fetchone()
            return float(row["total"]) if row else 0.0

    @staticmethod
    def get_upcoming(business_id: int = 1, limit: int = 10) -> List[Dict]:
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT a.*, l.name as lead_name, l.phone as lead_phone
                   FROM appointments a JOIN leads l ON a.lead_id=l.id
                   WHERE l.business_id=? AND a.scheduled_at >= CURRENT_TIMESTAMP
                   AND a.status NOT IN ('cancelled','no_show')
                   ORDER BY a.scheduled_at ASC LIMIT ?""",
                (business_id, limit)
            ).fetchall()
            return [row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────────────────────

class ConversationCRM:
    @staticmethod
    def get_or_create(session_id: str, lead_id: Optional[int] = None) -> Dict:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE session_id=?", (session_id,)
            ).fetchone()
            if row:
                return row_to_dict(row)
            cur = conn.execute(
                "INSERT INTO conversations (session_id, lead_id, messages) VALUES (?,?,?)",
                (session_id, lead_id, "[]")
            )
            return {"id": cur.lastrowid, "session_id": session_id,
                    "lead_id": lead_id, "messages": "[]"}

    @staticmethod
    def append_message(session_id: str, role: str, content: str,
                       lead_id: Optional[int] = None):
        """Append a message to the conversation log."""
        with db_conn() as conn:
            row = conn.execute(
                "SELECT id, messages FROM conversations WHERE session_id=?",
                (session_id,)
            ).fetchone()
            if row:
                messages = json.loads(row["messages"] or "[]")
                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": datetime.utcnow().isoformat()
                })
                conn.execute(
                    "UPDATE conversations SET messages=?, updated_at=? WHERE session_id=?",
                    (json.dumps(messages), datetime.utcnow().isoformat(), session_id)
                )
            else:
                messages = [{"role": role, "content": content,
                             "timestamp": datetime.utcnow().isoformat()}]
                conn.execute(
                    "INSERT INTO conversations (session_id, lead_id, messages) VALUES (?,?,?)",
                    (session_id, lead_id, json.dumps(messages))
                )

    @staticmethod
    def get_messages(session_id: str) -> List[Dict]:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT messages FROM conversations WHERE session_id=?", (session_id,)
            ).fetchone()
            if not row:
                return []
            return json.loads(row["messages"] or "[]")

    @staticmethod
    def link_lead(session_id: str, lead_id: int):
        with db_conn() as conn:
            conn.execute(
                "UPDATE conversations SET lead_id=?, updated_at=? WHERE session_id=?",
                (lead_id, datetime.utcnow().isoformat(), session_id)
            )


# ─────────────────────────────────────────────────────────────────────────────
# Follow-Up Queue
# ─────────────────────────────────────────────────────────────────────────────

class FollowUpCRM:
    @staticmethod
    def enqueue(lead_id: int, follow_up_type: str,
                scheduled_at: str, message_template: str = "") -> Dict:
        with db_conn() as conn:
            cur = conn.execute(
                """INSERT INTO follow_up_queue (lead_id, follow_up_type, scheduled_at, message_template)
                   VALUES (?,?,?,?)""",
                (lead_id, follow_up_type, scheduled_at, message_template)
            )
            return {"id": cur.lastrowid}

    @staticmethod
    def get_due(limit: int = 50) -> List[Dict]:
        """Return pending follow-ups whose scheduled_at has passed."""
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT fq.*, l.name, l.phone, l.email, l.job_type, l.system_type,
                          l.issue_description, l.business_id
                   FROM follow_up_queue fq JOIN leads l ON fq.lead_id=l.id
                   WHERE fq.status='pending'
                   AND fq.scheduled_at <= CURRENT_TIMESTAMP
                   ORDER BY fq.scheduled_at ASC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [row_to_dict(r) for r in rows]

    @staticmethod
    def mark_sent(fq_id: int):
        with db_conn() as conn:
            conn.execute(
                "UPDATE follow_up_queue SET status='sent', sent_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), fq_id)
            )

    @staticmethod
    def mark_failed(fq_id: int):
        with db_conn() as conn:
            conn.execute(
                "UPDATE follow_up_queue SET status='failed' WHERE id=?", (fq_id,)
            )

    @staticmethod
    def count_pending() -> int:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM follow_up_queue WHERE status='pending'"
            ).fetchone()
            return row["n"] if row else 0

    @staticmethod
    def get_all() -> List[Dict]:
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT fq.*, l.name, l.phone FROM follow_up_queue fq
                   LEFT JOIN leads l ON fq.lead_id=l.id
                   ORDER BY fq.scheduled_at DESC"""
            ).fetchall()
            return [row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Reviews
# ─────────────────────────────────────────────────────────────────────────────

class ReviewCRM:
    @staticmethod
    def create(lead_id: int, appointment_id: Optional[int] = None,
               platform: str = "google") -> Dict:
        with db_conn() as conn:
            cur = conn.execute(
                """INSERT INTO reviews (lead_id, appointment_id, platform)
                   VALUES (?,?,?)""",
                (lead_id, appointment_id, platform)
            )
            return {"id": cur.lastrowid}

    @staticmethod
    def get_all() -> List[Dict]:
        with db_conn() as conn:
            rows = conn.execute(
                """SELECT r.*, l.name, l.phone FROM reviews r
                   LEFT JOIN leads l ON r.lead_id=l.id
                   ORDER BY r.requested_at DESC"""
            ).fetchall()
            return [row_to_dict(r) for r in rows]

    @staticmethod
    def update_status(review_id: int, status: str, message_sent: str = ""):
        with db_conn() as conn:
            conn.execute(
                "UPDATE reviews SET status=?, message_sent=? WHERE id=?",
                (status, message_sent, review_id)
            )

    @staticmethod
    def count_pending() -> int:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM reviews WHERE status='pending'"
            ).fetchone()
            return row["n"] if row else 0
