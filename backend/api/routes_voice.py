"""
routes_voice.py — Voice Ordering API Endpoints
================================================
/api/voice/* — Audio transcription, text ordering, order management
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from modules.voice.pipeline import process_voice_order

router = APIRouter()


@router.post("/order")
async def voice_order(
    audio: UploadFile = File(None),
    text: str = Form(None),
    session_id: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Process a voice order.

    Accepts either:
    - An audio file (WAV/MP3/WEBM) for STT processing
    - A text string for direct NLP processing
    """
    audio_path = None

    if audio and audio.filename:
        # Save uploaded audio to temp file
        suffix = Path(audio.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            audio_path = tmp.name

    result = process_voice_order(
        db=db,
        audio_path=audio_path,
        text_input=text,
        session_id=session_id,
    )

    # Clean up temp file
    if audio_path:
        Path(audio_path).unlink(missing_ok=True)

    return result


@router.post("/order/text")
def text_order(
    text: str,
    session_id: str = None,
    db: Session = Depends(get_db),
):
    """Process a text-based order (skip STT step)."""
    return process_voice_order(
        db=db,
        text_input=text,
        session_id=session_id,
    )
