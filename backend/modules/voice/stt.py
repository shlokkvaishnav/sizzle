"""
stt.py — faster-whisper Speech-to-Text Wrapper
================================================
Local STT using faster-whisper — no API calls.
Handles WAV/MP3 audio files from the voice recorder.
"""

import logging
from pathlib import Path

logger = logging.getLogger("petpooja.voice.stt")

# Lazy-loaded model (loaded on first use)
_model = None


def _get_model():
    """Lazy-load the faster-whisper model."""
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model (base)...")
            _model = WhisperModel(
                "base",        # Options: tiny, base, small, medium, large-v3
                device="cpu",  # Use "cuda" if GPU available
                compute_type="int8",
            )
            logger.info("faster-whisper model loaded successfully")
        except ImportError:
            logger.warning(
                "faster-whisper not installed. "
                "Install with: pip install faster-whisper"
            )
            _model = None
    return _model


def transcribe_audio(
    audio_path: str,
    language: str = "hi",
) -> str:
    """
    Transcribe an audio file to text using faster-whisper.

    Args:
        audio_path: Path to WAV/MP3/WEBM audio file
        language: Language hint ('hi' for Hindi, 'en' for English)

    Returns:
        Transcribed text string
    """
    model = _get_model()

    if model is None:
        logger.warning("No STT model available, returning empty string")
        return ""

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info(f"Transcribing: {path.name} (language={language})")

    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=5,
        word_timestamps=False,
        vad_filter=True,         # Voice Activity Detection
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=300,
        ),
    )

    # Collect all segments
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    transcription = " ".join(text_parts)
    logger.info(f"Transcription: {transcription[:80]}...")
    return transcription


def transcribe_bytes(
    audio_bytes: bytes,
    language: str = "hi",
) -> str:
    """
    Transcribe audio bytes (e.g., from a WebSocket stream).
    Saves to a temp file and transcribes.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        return transcribe_audio(tmp_path, language)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
