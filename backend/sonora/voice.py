"""
sonora/voice.py — Sonora Voice Layer
Text-to-Speech (OpenAI TTS, voice: nova) and Speech-to-Text (Whisper).
Degrades gracefully when no API key is configured.
"""

import io
import os
import base64
import logging
import hashlib
import tempfile
from typing import Optional, Union, Tuple

from config import config

logger = logging.getLogger(__name__)

# Audio cache directory (in-memory for simple caching)
_tts_cache: dict = {}


def _get_openai_client():
    """Lazy-init OpenAI client."""
    if not config.has_openai():
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=config.OPENAI_API_KEY)
    except ImportError:
        logger.warning("openai package not installed — voice features unavailable")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Text-to-Speech
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_speech(
    text: str,
    voice: str = None,
    model: str = None,
    speed: float = 1.0,
    output_format: str = "mp3",
    use_cache: bool = True,
) -> Tuple[Optional[bytes], str]:
    """
    Convert text to speech using OpenAI TTS (voice: nova by default).

    Returns:
        (audio_bytes, content_type) — audio_bytes is None on failure
    """
    voice = voice or config.TTS_VOICE      # default: nova
    model = model or config.TTS_MODEL      # default: tts-1
    content_type = f"audio/{output_format}"

    if not text or not text.strip():
        return None, content_type

    # Cache key
    cache_key = hashlib.md5(f"{text}{voice}{model}{speed}{output_format}".encode()).hexdigest()
    if use_cache and cache_key in _tts_cache:
        logger.debug("TTS cache hit for key %s", cache_key[:8])
        return _tts_cache[cache_key], content_type

    client = _get_openai_client()
    if not client:
        logger.warning("TTS unavailable — no OpenAI client")
        return None, content_type

    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            speed=speed,
            response_format=output_format,
        )
        audio_bytes = response.content

        if use_cache:
            _tts_cache[cache_key] = audio_bytes

        logger.info("TTS synthesized %d chars → %d bytes audio", len(text), len(audio_bytes))
        return audio_bytes, content_type

    except Exception as e:
        logger.error("TTS synthesis error: %s", e)
        return None, content_type


def synthesize_speech_b64(text: str, voice: str = None, **kwargs) -> Optional[str]:
    """
    Synthesize speech and return base64-encoded audio string,
    suitable for embedding in JSON responses as a data URI.
    Returns None on failure.
    """
    audio_bytes, content_type = synthesize_speech(text, voice=voice, **kwargs)
    if not audio_bytes:
        return None
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


def save_speech_to_file(text: str, filepath: str, voice: str = None, **kwargs) -> bool:
    """
    Synthesize speech and save to a file.
    Returns True on success, False on failure.
    """
    audio_bytes, _ = synthesize_speech(text, voice=voice, **kwargs)
    if not audio_bytes:
        return False
    try:
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        return True
    except IOError as e:
        logger.error("Error saving speech to %s: %s", filepath, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Speech-to-Text (Whisper)
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribe audio using OpenAI Whisper.

    Args:
        audio_bytes: Raw audio file bytes (webm, mp3, wav, ogg, mp4, m4a, flac)
        filename: Filename hint for format detection (must have correct extension)
        language: Optional ISO-639-1 language code (e.g. 'en')
        prompt: Optional context prompt to improve accuracy (e.g. "HVAC technician call")

    Returns:
        Transcription text, or None on failure
    """
    client = _get_openai_client()
    if not client:
        logger.warning("Transcription unavailable — no OpenAI client")
        return None

    if not audio_bytes:
        return None

    try:
        # Whisper needs a file-like object with a name attribute
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        kwargs = {
            "model": config.WHISPER_MODEL,
            "file": audio_file,
        }
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        result = client.audio.transcriptions.create(**kwargs)
        text = result.text.strip()
        logger.info("Transcribed %d bytes → %d chars", len(audio_bytes), len(text))
        return text

    except Exception as e:
        logger.error("Transcription error: %s", e)
        return None


def transcribe_audio_b64(
    audio_b64: str,
    filename: str = "audio.webm",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribe base64-encoded audio (e.g. from a web client).
    Strips data URI prefix if present.
    """
    try:
        # Strip data URI header if present (data:audio/webm;base64,...)
        if "," in audio_b64:
            audio_b64 = audio_b64.split(",", 1)[1]
        audio_bytes = base64.b64decode(audio_b64)
        return transcribe_audio(audio_bytes, filename=filename,
                                language=language, prompt=prompt)
    except Exception as e:
        logger.error("Error decoding base64 audio: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Voice Pipeline: Audio In → Sonora Chat → Audio Out
# ─────────────────────────────────────────────────────────────────────────────

def process_voice_turn(
    audio_bytes: bytes,
    session_id: str,
    agent,
    audio_filename: str = "audio.webm",
    business_id: int = 1,
) -> dict:
    """
    Full voice pipeline:
      1. Transcribe user audio
      2. Send transcript to SonoraAgent.chat()
      3. Synthesize Sonora's response as audio
      4. Return everything as a dict

    Returns:
        {
            "transcript": str,
            "response_text": str,
            "audio_b64": str | None,
            "lead_data": dict,
            "success": bool
        }
    """
    result = {
        "transcript": None,
        "response_text": None,
        "audio_b64": None,
        "lead_data": {},
        "success": False,
    }

    # Step 1: Transcribe
    transcript = transcribe_audio(
        audio_bytes,
        filename=audio_filename,
        prompt="HVAC customer service call, could mention AC, furnace, heating, cooling issues"
    )
    if not transcript:
        result["response_text"] = (
            "I'm sorry, I had a little trouble hearing you. Could you say that again?"
        )
        audio_b64 = synthesize_speech_b64(result["response_text"])
        result["audio_b64"] = audio_b64
        return result

    result["transcript"] = transcript

    # Step 2: Chat
    try:
        response_text, lead_data = agent.chat(
            session_id=session_id,
            message=transcript,
            business_id=business_id
        )
        result["response_text"] = response_text
        result["lead_data"] = lead_data
    except Exception as e:
        logger.error("Agent chat error in voice pipeline: %s", e)
        result["response_text"] = (
            "I'm here to help! Could you tell me your name and what's going on with your system?"
        )

    # Step 3: Synthesize response
    if result["response_text"]:
        result["audio_b64"] = synthesize_speech_b64(result["response_text"])

    result["success"] = bool(result["transcript"] and result["response_text"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Utility: Sonora voice check
# ─────────────────────────────────────────────────────────────────────────────

def voice_health_check() -> dict:
    """
    Returns status of voice capabilities.
    """
    return {
        "tts_available": config.has_openai(),
        "transcription_available": config.has_openai(),
        "tts_voice": config.TTS_VOICE,
        "tts_model": config.TTS_MODEL,
        "whisper_model": config.WHISPER_MODEL,
        "cache_entries": len(_tts_cache),
    }


def clear_tts_cache():
    """Clear the in-memory TTS cache."""
    _tts_cache.clear()
    logger.info("TTS cache cleared")
