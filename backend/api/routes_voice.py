"""
routes_voice.py — Voice Ordering API Endpoints
================================================
/api/voice/* — Transcription, full pipeline processing,
order confirmation, and order history.
"""

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import Order
from modules.voice.order_builder import build_order, generate_kot, save_order_to_db

router = APIRouter()


def _get_pipeline(db: Session = Depends(get_db)):
    """Get VoicePipeline from app state (loaded at startup with DB data)."""
    from main import app
    pipeline = getattr(app.state, "voice_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Voice pipeline not loaded")
    return pipeline


class TextInput(BaseModel):
    text: str
    session_id: str | None = None


class ConfirmOrderInput(BaseModel):
    order: dict
    kot: dict | None = None


# ── 1. POST /api/voice/transcribe ──

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
):
    """
    Audio → transcript only (no order processing).
    Returns: {transcript, detected_language, confidence}
    """
    audio_path = None
    try:
        suffix = Path(audio.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            audio_path = tmp.name

        from modules.voice.stt import transcribe
        result = transcribe(audio_path)

        return {
            "transcript": result.get("transcript", ""),
            "detected_language": result.get("detected_language", "en"),
            "confidence": result.get("language_confidence", 0.0),
        }
    except Exception as e:
        return {"transcript": "", "error": str(e)}
    finally:
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)


# ── 2. POST /api/voice/process-audio ──

@router.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Full pipeline: audio → transcript → parsed order → upsell suggestions.
    Returns: {transcript, intent, items, order, upsell_suggestions}
    """
    pipeline = _get_pipeline(db)
    audio_path = None
    try:
        suffix = Path(audio.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            audio_path = tmp.name

        return pipeline.process_audio(audio_path)
    except Exception as e:
        return {"error": str(e), "order": None, "items": [], "upsell_suggestions": []}
    finally:
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)


# ── 3. POST /api/voice/process ──

@router.post("/process")
def process_text(
    body: TextInput,
    db: Session = Depends(get_db),
):
    """
    Text → full pipeline result (for testing without microphone).
    Accepts: {text: string}
    Returns: same as /process-audio but from text input
    """
    pipeline = _get_pipeline(db)
    return pipeline.process_text(body.text)


# ── 4. POST /api/voice/confirm-order ──

@router.post("/confirm-order")
def confirm_order(
    body: ConfirmOrderInput,
    db: Session = Depends(get_db),
):
    """
    Save confirmed order to DB.
    Accepts: {order: {...}}
    Returns: {order_id, kot}
    """
    order = body.order
    kot = body.kot

    # Generate KOT if not provided
    if not kot:
        kot = generate_kot(order)

    # Save to database
    try:
        result = save_order_to_db(order, kot, db)
        return {
            "success": True,
            "order_id": result["order_id"],
            "kot_id": result["kot_id"],
            "kot": kot,
            "status": "confirmed",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 5. GET /api/voice/orders ──

@router.get("/orders")
def get_recent_orders(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Recent orders list (last 50), sorted by created_at desc.
    """
    orders = (
        db.query(Order)
        .order_by(desc(Order.created_at))
        .limit(limit)
        .all()
    )

    return {
        "orders": [
            {
                "order_id": o.order_id,
                "order_number": o.order_number,
                "total_amount": o.total_amount,
                "status": o.status,
                "order_type": o.order_type,
                "table_number": o.table_number,
                "source": o.source,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
        "count": len(orders),
    }


# ── Legacy endpoint for backward compatibility ──

@router.post("/order")
async def voice_order_legacy(
    audio: UploadFile = File(None),
    text: str = None,
    db: Session = Depends(get_db),
):
    """Legacy endpoint — process voice or text order."""
    pipeline = _get_pipeline(db)

    if audio and audio.filename:
        suffix = Path(audio.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            audio_path = tmp.name
        try:
            return pipeline.process_audio(audio_path)
        finally:
            Path(audio_path).unlink(missing_ok=True)
    elif text:
        return pipeline.process_text(text)
    else:
        return {"error": "Provide audio file or text input"}
