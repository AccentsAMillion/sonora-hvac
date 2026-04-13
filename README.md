# Sonora — The Voice of Your Business

> The 24/7 AI Growth Engine for HVAC companies. Sonora answers every call, qualifies every lead, books every job, and follows up automatically — so HVAC owners stop losing revenue to voicemail and slow follow-up.

---

## The Problem Sonora Solves

| Pain Point | Impact |
|-----------|--------|
| 35% of HVAC calls go to voicemail | Each missed install = $4,500–$12,000 lost |
| Manual follow-up converts at ~20% | Sonora's automated sequences convert at 3x |
| CSRs spend hours on qualification | Sonora handles it in 2 minutes, 24/7 |
| Review requests never get sent | Sonora sends them automatically post-job |

---

## What Sonora Does

```
Homeowner calls/texts → Sonora answers instantly
       ↓
Qualifies: name, job type, system, urgency (1–10 score)
       ↓
Emergency detected (score ≥ 8)? → Escalation flow
       ↓
Books appointment → Confirms with homeowner
       ↓
Sends reminders (24hr + 2hr before)
       ↓
Job complete → Review request fires automatically
       ↓
No response? → 2min SMS → 24hr → 3-day → 7-day nurture
```

---

## Architecture

```
┌────────────────────────────────────────────┐
│            SONORA FRONTEND                  │
│  index.html   — Sales/demo landing page    │
│  dashboard.html — Owner command center     │
│  sonora-widget.js — Embeddable chat widget │
└──────────────────┬─────────────────────────┘
                   │ REST API
┌──────────────────▼─────────────────────────┐
│         FLASK BACKEND (app.py)             │
│  15 endpoints: chat, voice, leads,         │
│  appointments, follow-up, dashboard        │
└───┬──────────┬──────────┬──────────────────┘
    │          │          │
┌───▼──┐ ┌────▼───┐ ┌────▼────────────────┐
│agent │ │voice.py│ │crm.py  follow_up.py │
│GPT-4o│ │TTS nova│ │SQLite  APScheduler  │
│7-step│ │Whisper │ │CRM     GHL sync     │
│state │ │        │ │        SMS/email    │
└──────┘ └────────┘ └─────────────────────┘
```

---

## Quick Start

```bash
git clone https://github.com/AccentsAMillion/sonora-hvac
cd sonora-hvac/backend

pip install -r requirements.txt
cp .env.example .env        # Add OPENAI_API_KEY
python seed_data.py         # Loads Desert Air HVAC demo data
python app.py               # Starts on port 5000
```

Open `frontend/index.html` to see the landing page or `frontend/dashboard.html` for the owner command center.

---

## Sonora's Personality

Sonora is the "Voice of the Business" — not a bot, not a menu system.

- **Warm and confident**: Makes every homeowner feel heard
- **HVAC-fluent**: Knows the difference between a refrigerant leak and a blower motor
- **Urgency-aware**: Detects emergencies and escalates immediately
- **Never robotic**: Every message sounds personal, even at 2am

Example conversation:
> **Homeowner**: "My AC stopped working and it's 108 degrees outside"
> **Sonora**: "Oh no — that's an emergency and I'm going to get someone to you as fast as possible. Can I grab your address and confirm your system is a central AC unit?"

---

## Demo Data

Seeded with **Desert Air HVAC — Phoenix, AZ**:
- 15 leads (repair, install, maintenance, emergency — all stages)
- 8 appointments ($6,537 estimated pipeline revenue)
- 3 live conversations showing Sonora qualifying leads
- 8 follow-up tasks in queue
- 4 review requests

---

## Conversation State Machine

```
GREETING → QUALIFICATION → URGENCY_CHECK → BOOKING
                                ↓
                          (score ≥ 8)
                                ↓
                          EMERGENCY ESCALATION
                                ↓
              CONFIRMATION → FOLLOW_UP → REVIEW_REQUEST
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message to Sonora |
| POST | `/api/voice` | Voice input → response + audio |
| GET | `/api/leads` | All leads |
| POST | `/api/leads` | Create lead manually |
| GET | `/api/appointments` | All appointments |
| POST | `/api/appointments` | Book appointment |
| GET | `/api/dashboard` | Owner dashboard stats |
| POST | `/api/tts` | Text → Sonora's voice |
| POST | `/api/sms/send` | Send SMS via Twilio |
| GET | `/api/reviews` | Review request queue |
| POST | `/api/reactivate` | Trigger reactivation campaign |
| POST | `/api/webhook/ghl` | GoHighLevel webhook |

---

## Replacing Sonora's Voice

Currently uses OpenAI's `nova` voice. To swap in a cloned voice:
1. Clone in ElevenLabs (30–60 seconds of clean audio needed)
2. Set `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in `.env`
3. Update `sonora/voice.py` to route to ElevenLabs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI | OpenAI GPT-4o + function calling |
| Voice | OpenAI TTS (nova) + Whisper |
| Backend | Python / Flask |
| Database | SQLite (PostgreSQL-ready) |
| Scheduler | APScheduler (follow-up engine) |
| CRM Sync | GoHighLevel API |
| SMS | Twilio |
| Frontend | HTML/CSS/JS + Chart.js |

---

## Pricing Model

| Tier | Price | What's Included |
|------|-------|----------------|
| Core Engine | $1,500/mo | AI receptionist + booking + follow-up |
| Growth Engine | $2,500/mo | + Smart dispatch + review automation |
| Full Modernization | $3,500/mo | + Reactivation + dashboard + custom integrations |
| Setup | $5,000–$7,500 one-time | Build, configure, go-live |
