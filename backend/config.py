"""
config.py — Sonora HVAC Backend Configuration
Loads environment variables with sensible defaults.
App runs with just OPENAI_API_KEY; all other integrations degrade gracefully.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Core ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sonora-dev-secret-change-in-prod")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "sonora_hvac.db")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    TTS_VOICE: str = os.getenv("TTS_VOICE", "nova")
    TTS_MODEL: str = os.getenv("TTS_MODEL", "tts-1")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")

    # ── Twilio ────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

    # ── GoHighLevel ───────────────────────────────────────────────────────────
    GHL_API_KEY: str = os.getenv("GHL_API_KEY", "")
    GHL_LOCATION_ID: str = os.getenv("GHL_LOCATION_ID", "")
    GHL_WEBHOOK_SECRET: str = os.getenv("GHL_WEBHOOK_SECRET", "")

    # ── Follow-Up Engine ─────────────────────────────────────────────────────
    MISSED_CALL_DELAY_SECONDS: int = int(os.getenv("MISSED_CALL_DELAY_SECONDS", "120"))
    FOLLOWUP_ENGINE_INTERVAL_SECONDS: int = int(
        os.getenv("FOLLOWUP_ENGINE_INTERVAL_SECONDS", "60")
    )

    # ── Feature flags (auto-detected from credentials) ───────────────────────
    @classmethod
    def has_openai(cls) -> bool:
        return bool(cls.OPENAI_API_KEY)

    @classmethod
    def has_twilio(cls) -> bool:
        return bool(cls.TWILIO_ACCOUNT_SID and cls.TWILIO_AUTH_TOKEN and cls.TWILIO_FROM_NUMBER)

    @classmethod
    def has_ghl(cls) -> bool:
        return bool(cls.GHL_API_KEY and cls.GHL_LOCATION_ID)


config = Config()
