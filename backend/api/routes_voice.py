"""
routes_voice.py — Voice Ordering API Endpoints
================================================
/api/voice/* — Transcription, full pipeline processing,
order confirmation, order history, and WebSocket streaming.

Auth note for /stream (WebSocket)
----------------------------------
Browsers CANNOT send custom HTTP headers (e.g. Authorization: Bearer ...)
on WebSocket upgrade requests — it is a browser security restriction.
Therefore the /stream endpoint handles auth itself: when AUTH_ENABLED=true
it reads an optional JWT from the `token` query parameter:

  ws://host/api/voice/stream?token=<jwt>

When AUTH_ENABLED=false (development default) the check is skipped.
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from api.auth import AUTH_ENABLED, verify_token
from api.deps import get_voice_pipeline
from database import get_db
from models import Order
from modules.voice.order_builder import build_order, generate_kot, save_order_to_db
from modules.voice.voice_config import cfg

router = APIRouter()
logger = logging.getLogger("petpooja.api.voice")

# Max audio file size (default 10 MB)
_MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE_BYTES", str(10 * 1024 * 1024)))
_ALLOWED_EXTENSIONS = {".wav", ".mp3", ".ogg", ".webm", ".m4a", ".flac"}
_AUDIO_READ_CHUNK_SIZE = int(os.getenv("AUDIO_READ_CHUNK_SIZE", str(1024 * 1024)))


class TextInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    restaurant_id: int | None = None


class ConfirmOrderInput(BaseModel):
    order: dict
    kot: dict | None = None


class SpeakInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    language: str = Field(default="en", pattern=r"^(en|hi|gu|mr|kn)$")


async def _save_audio_temp(audio: UploadFile) -> str:
    """Validate and save uploaded audio to a temp file. Returns path."""
    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{suffix}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # Fast reject if client sends a valid Content-Length header.
    content_length = audio.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_AUDIO_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Audio file too large ({content_length} bytes). Max: {_MAX_AUDIO_SIZE} bytes.",
                )
        except ValueError:
            # Ignore invalid header and fall back to streamed validation.
            pass

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    total_bytes = 0
    try:
        while True:
            chunk = await audio.read(_AUDIO_READ_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_AUDIO_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"Audio file too large ({total_bytes} bytes). Max: {_MAX_AUDIO_SIZE} bytes.",
                )
            tmp.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Empty audio file.")

        tmp.flush()
        return tmp.name
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise
    finally:
        tmp.close()


# ── 1. POST /api/voice/transcribe ──

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
):
    """
    Audio → transcript only (no order processing).
    Returns: {transcript, detected_language, confidence}
    """
    audio_path = await _save_audio_temp(audio)
    try:
        from modules.voice.stt import transcribe
        from modules.voice import pipeline_errors as errs

        result = transcribe(audio_path)

        stage_results = []
        user_messages = []

        is_low = result.get("is_low_confidence", False)
        reason = result.get("low_confidence_reason")

        if is_low and reason:
            sr_map = {
                "no_speech_detected": errs.stt_no_speech,
                "empty_transcript": errs.stt_no_speech,
                "below_threshold": errs.stt_low_confidence,
            }
            factory = sr_map.get(reason)
            if factory:
                sr = factory()
                stage_results.append(sr.to_dict())
                user_messages.append(sr.user_message)

        return {
            "transcript": result.get("transcript", ""),
            "detected_language": result.get("detected_language", "en"),
            "confidence": result.get("language_confidence", 0.0),
            "transcription_confidence": result.get("transcription_confidence", 0.0),
            "is_low_confidence": is_low,
            "low_confidence_reason": reason,
            "segments": result.get("segments", []),
            "vad_info": result.get("vad_info"),
            "stage_results": stage_results,
            "user_messages": user_messages,
        }
    except FileNotFoundError:
        logger.exception("Audio file not found")
        raise HTTPException(status_code=400, detail="Audio file could not be processed")
    except RuntimeError as e:
        logger.exception("STT model error")
        raise HTTPException(status_code=503, detail=f"Speech recognition unavailable: {e}")
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    finally:
        Path(audio_path).unlink(missing_ok=True)


# ── 2. POST /api/voice/process-audio ──

@router.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    session_id: str = Form(None),
    language: str = Form(None),
    restaurant_id: int = Form(None),
    pipeline=Depends(get_voice_pipeline),
):
    """
    Full pipeline: audio → transcript → parsed order → upsell suggestions.
    Returns: {transcript, intent, items, order, upsell_suggestions}
    """
    import time as _time
    t0 = _time.perf_counter()

    audio_path = await _save_audio_temp(audio)
    try:
        result = await asyncio.to_thread(
            pipeline.process_audio, audio_path,
            session_id=session_id,
            language_hint=language or None,
            restaurant_id=restaurant_id,
        )

        t_pipeline = _time.perf_counter() - t0

        # TTS enhancement — with timeout to prevent TTS from blocking response
        tts_result = {"audio_b64": None, "spoken_text": None, "language": result.get("detected_language", "en")}
        t_tts = 0.0
        if cfg.TTS_ENABLED:
            try:
                from modules.voice.tts import tts_orchestrator
                detected_lang = result.get("detected_language", "en")
                t_tts_start = _time.perf_counter()
                tts_result = await asyncio.wait_for(
                    tts_orchestrator.get_audio_response(result, detected_lang),
                    timeout=3.0,  # hard cap TTS at 3s
                )
                t_tts = _time.perf_counter() - t_tts_start
                logger.info("⏱ TTS completed in %.1fms", t_tts * 1000)
            except asyncio.TimeoutError:
                logger.warning("TTS timed out (3s cap) — returning without audio")
            except Exception as e:
                logger.warning(f"TTS enhancement failed: {e}")

        result["tts_audio_b64"] = tts_result["audio_b64"]
        result["tts_text"] = tts_result["spoken_text"]
        result["tts_language"] = tts_result["language"]

        total_ms = (_time.perf_counter() - t0) * 1000
        result["total_time_ms"] = round(total_ms, 1)

        # ── Build per-stage timing block ─────────────────────────────────────
        stt_ms   = result.pop("_stt_ms", None)
        ffmpeg_ms = result.pop("_ffmpeg_ms", None)
        whisper_ms = result.pop("_whisper_ms", None)
        nlp_ms   = result.pop("_nlp_ms", result.get("timing_ms"))
        result["timing"] = {
            "stt_ms":     round(stt_ms, 1)    if stt_ms    is not None else None,
            "ffmpeg_ms":  round(ffmpeg_ms, 1) if ffmpeg_ms is not None else None,
            "whisper_ms": round(whisper_ms, 1) if whisper_ms is not None else None,
            "nlp_ms":     round(nlp_ms, 1)    if nlp_ms    is not None else None,
            "tts_ms":     round(t_tts * 1000, 1),
            "total_ms":   round(total_ms, 1),
        }

        logger.info("⏱ Total /process-audio in %.1fms (stt=%.1fms, nlp=%.1fms, tts=%.1fms)",
                    total_ms,
                    stt_ms   or 0,
                    nlp_ms   or 0,
                    t_tts * 1000)

        return result
    except FileNotFoundError:
        logger.exception("Audio file not found during processing")
        raise HTTPException(status_code=400, detail="Audio file could not be read")
    except RuntimeError as e:
        logger.exception("STT model error during pipeline")
        raise HTTPException(status_code=503, detail=f"Speech recognition unavailable: {e}")
    except ValueError as e:
        logger.exception("Pipeline parsing error")
        raise HTTPException(status_code=422, detail=f"Could not parse order: {e}")
    except Exception as e:
        logger.exception("Voice pipeline failed")
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {e}")
    finally:
        Path(audio_path).unlink(missing_ok=True)


# ── 3. POST /api/voice/process ──

@router.post("/process")
async def process_text(
    body: TextInput,
    pipeline=Depends(get_voice_pipeline),
):
    """
    Text → full pipeline result (for testing without microphone).
    Accepts: {text: string}
    Returns: same as /process-audio but from text input
    """
    try:
        import time as _time
        t0 = _time.perf_counter()

        result = pipeline.process_text(body.text, session_id=body.session_id,
                                       restaurant_id=body.restaurant_id)

        # TTS enhancement — with timeout cap
        tts_result = {"audio_b64": None, "spoken_text": None, "language": result.get("detected_language", "en")}
        t_tts = 0.0
        if cfg.TTS_ENABLED:
            try:
                from modules.voice.tts import tts_orchestrator
                detected_lang = result.get("detected_language", "en")
                t_tts_start = _time.perf_counter()
                tts_result = await asyncio.wait_for(
                    tts_orchestrator.get_audio_response(result, detected_lang),
                    timeout=3.0,
                )
                t_tts = _time.perf_counter() - t_tts_start
            except asyncio.TimeoutError:
                logger.warning("TTS timed out (3s cap) — returning without audio")
            except Exception as e:
                logger.warning(f"TTS enhancement failed: {e}")

        result["tts_audio_b64"] = tts_result["audio_b64"]
        result["tts_text"] = tts_result["spoken_text"]
        result["tts_language"] = tts_result["language"]

        total_ms = (_time.perf_counter() - t0) * 1000
        result["total_time_ms"] = round(total_ms, 1)

        # ── Build per-stage timing block ─────────────────────────────────────
        nlp_ms = result.pop("_nlp_ms", result.get("timing_ms"))
        result.pop("_stt_ms", None)    # text input has no STT
        result.pop("_ffmpeg_ms", None)
        result.pop("_whisper_ms", None)
        result["timing"] = {
            "stt_ms":    None,           # text input — no STT phase
            "ffmpeg_ms": None,
            "whisper_ms": None,
            "nlp_ms":    round(nlp_ms, 1) if nlp_ms is not None else None,
            "tts_ms":    round(t_tts * 1000, 1),
            "total_ms":  round(total_ms, 1),
        }

        logger.info("⏱ Total /process in %.1fms (nlp=%.1fms, tts=%.1fms)",
                    total_ms, nlp_ms or 0, t_tts * 1000)
        return result
    except ValueError as e:
        logger.exception("Text parsing error")
        raise HTTPException(status_code=422, detail=f"Could not parse order: {e}")
    except Exception as e:
        logger.exception("Text processing failed")
        raise HTTPException(status_code=500, detail=f"Text processing failed: {e}")


# ── 3b. POST /api/voice/speak ──

@router.post("/speak")
async def speak_text(
    body: SpeakInput,
):
    """
    Text + language → TTS audio.
    Use cases: re-play last response, read upsell banners, price recommendations.
    Returns: {audio_b64, text}
    """
    if not cfg.TTS_ENABLED:
        raise HTTPException(status_code=503, detail="TTS is disabled")

    try:
        from modules.voice.tts import tts_orchestrator
        result = await tts_orchestrator.speak_text(body.text, body.language)
        if result["audio_b64"] is None:
            raise HTTPException(status_code=503, detail="TTS engine not ready")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("speak_text failed")
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")


# ── 4. POST /api/voice/confirm-order ──

@router.post("/confirm-order")
def confirm_order(
    body: ConfirmOrderInput,
    restaurant_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Save confirmed order to DB.
    Accepts: {order: {...}}
    Returns: {order_id, kot}
    """
    order = body.order
    if not order or not order.get("items"):
        raise HTTPException(status_code=400, detail="Order must contain items.")

    kot = body.kot
    if not kot:
        kot = generate_kot(order)

    try:
        result = save_order_to_db(order, kot, db, restaurant_id=restaurant_id)
        return {
            "success": True,
            "order_id": result["order_id"],
            "kot_id": result["kot_id"],
            "kot": kot,
            "status": "confirmed",
        }
    except Exception as e:
        logger.exception("Order confirmation failed")
        raise HTTPException(status_code=500, detail=f"Order save failed: {e}")


# ── 5. GET /api/voice/orders ──

@router.get("/orders")
def get_recent_orders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    restaurant_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Recent orders with pagination, sorted by created_at desc.
    """
    q = db.query(Order)
    if restaurant_id:
        q = q.filter(Order.restaurant_id == restaurant_id)

    total = q.count()

    orders = (
        q.order_by(desc(Order.created_at))
        .offset(offset)
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
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ── Legacy endpoint for backward compatibility ──

@router.post("/order")
async def voice_order_legacy(
    audio: UploadFile = File(None),
    text: str = None,
    session_id: str = None,
    pipeline=Depends(get_voice_pipeline),
):
    """Legacy endpoint — process voice or text order."""
    audio_path = None

    try:
        if audio and audio.filename:
            audio_path = await _save_audio_temp(audio)
            return pipeline.process_audio(audio_path, session_id=session_id)
        elif text:
            return pipeline.process_text(text, session_id=session_id)
        else:
            raise HTTPException(status_code=400, detail="Provide audio file or text input")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Legacy voice order failed")
        raise HTTPException(status_code=500, detail=f"Voice order failed: {e}")


# ── 7. WebSocket /api/voice/stream — Real-time Voice Streaming ──

class _AudioBuffer:
    """Accumulates audio chunks and detects end-of-utterance via silence."""

    def __init__(self, silence_threshold_ms: int = 1500, max_buffer_ms: int = 15000):
        self._chunks: list[bytes] = []
        self._total_bytes: int = 0
        self._silence_ms = silence_threshold_ms
        self._max_ms = max_buffer_ms
        self._last_chunk_time: float = 0
        self._started: bool = False
        import time
        self._time = time

    def append(self, chunk: bytes):
        self._chunks.append(chunk)
        self._total_bytes += len(chunk)
        self._last_chunk_time = self._time.time()
        if not self._started:
            self._started = True

    def is_end_of_utterance(self) -> bool:
        """True if enough silence has passed since the last chunk arrived."""
        if not self._started or not self._chunks:
            return False
        elapsed_ms = (self._time.time() - self._last_chunk_time) * 1000
        return elapsed_ms >= self._silence_ms

    def is_max_reached(self) -> bool:
        """True if we've accumulated too much audio."""
        # Rough estimate: 16kHz mono 16-bit = 32KB/sec
        return self._total_bytes > (self._max_ms / 1000) * 32000

    def flush(self) -> bytes:
        """Return accumulated audio and reset buffer."""
        data = b"".join(self._chunks)
        self._chunks.clear()
        self._total_bytes = 0
        self._started = False
        return data

    @property
    def has_data(self) -> bool:
        return self._total_bytes > 0



async def voice_stream(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """
    WebSocket endpoint for real-time voice streaming.

    Auth: browsers cannot set Authorization headers on WS upgrades.
    When AUTH_ENABLED=true, pass JWT as a query param: ?token=<jwt>.
    When AUTH_ENABLED=false (dev default), no auth is required.

    Client sends:
    - Binary frames: raw audio chunks (PCM/WebM, ~250ms each)
    - JSON text frames: control messages
        {"type": "config", "session_id": "...", "language": "hi", "restaurant_id": 1}
        {"type": "interrupt"}  — cancel in-progress processing
        {"type": "end"}       — signal end of utterance manually

    Server sends JSON text frames:
        {"type": "partial_transcript", "text": "butter na...", "is_final": false}
        {"type": "final_transcript", "text": "butter naan aur dal", "is_final": true}
        {"type": "pipeline_result", ...full pipeline result...}
        {"type": "tts_chunk", "audio_b64": "...", "is_last": true/false}
        {"type": "error", "detail": "..."}
    """
    # ── WebSocket-compatible auth check ──────────────────────────────────────
    # Must accept() BEFORE sending any error response (WS protocol requirement).
    await websocket.accept()

    if AUTH_ENABLED:
        if not token:
            await websocket.send_json({
                "type": "error",
                "detail": "Authentication required. Pass JWT as ?token=... query param.",
            })
            await websocket.close(code=4401)
            return
        try:
            verify_token(token)
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "detail": exc.detail})
            await websocket.close(code=4401)
            return

    logger.info("WebSocket voice stream connected")

    # Session config
    session_id = None
    language = None
    restaurant_id = None
    audio_buf = _AudioBuffer()
    processing = False

    # Get pipeline from app state
    pipeline = getattr(websocket.app.state, "voice_pipeline", None)
    if pipeline is None:
        await websocket.send_json({"type": "error", "detail": "Voice pipeline not loaded"})
        await websocket.close(code=1011)
        return

    try:
        while True:
            msg = await websocket.receive()

            # Text frame → control message
            if "text" in msg:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                    continue

                msg_type = data.get("type", "")

                if msg_type == "config":
                    session_id = data.get("session_id", session_id)
                    language = data.get("language", language)
                    restaurant_id = data.get("restaurant_id", restaurant_id)
                    await websocket.send_json({"type": "config_ack", "session_id": session_id})

                elif msg_type == "interrupt":
                    audio_buf.flush()
                    processing = False
                    await websocket.send_json({"type": "interrupted"})

                elif msg_type == "end":
                    # Manual end-of-utterance signal
                    if audio_buf.has_data and not processing:
                        processing = True
                        await _process_ws_audio(
                            websocket, pipeline, audio_buf.flush(),
                            session_id, language, restaurant_id,
                        )
                        processing = False

            # Binary frame → audio chunk
            elif "bytes" in msg:
                chunk = msg["bytes"]
                if not chunk:
                    continue

                audio_buf.append(chunk)

                # Check for end of utterance (silence detection)
                # Note: actual silence detection requires analyzing audio energy,
                # which we approximate by checking time gaps between chunks.
                # The frontend should ideally send an "end" message when VAD detects silence.

                if audio_buf.is_max_reached():
                    if not processing:
                        processing = True
                        await _process_ws_audio(
                            websocket, pipeline, audio_buf.flush(),
                            session_id, language, restaurant_id,
                        )
                        processing = False

    except WebSocketDisconnect:
        logger.info("WebSocket voice stream disconnected")
    except Exception as e:
        logger.exception("WebSocket stream error: %s", e)
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass


async def _process_ws_audio(
    websocket: WebSocket,
    pipeline,
    audio_data: bytes,
    session_id: str = None,
    language: str = None,
    restaurant_id: int = None,
):
    """
    Process accumulated audio buffer and stream results back via WebSocket.

    Optimized pipeline:
    1. Run STT + NLP pipeline in thread pool (CPU-bound)
    2. Send pipeline_result to client immediately
    3. Generate spoken text (LLM/template) — fast, in async context
    4. Stream TTS audio chunks to client AS they are produced by edge-tts
       Client starts playing the first chunk ~500ms before synthesis is complete.
    """
    if not audio_data:
        return

    suffix = ".webm"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(audio_data)
        tmp.flush()
        tmp.close()

        import time as _time

        # ── Step 1: Send "thinking" indicator ────────────────────────────────
        await websocket.send_json({
            "type": "partial_transcript",
            "text": "...",
            "is_final": False,
        })

        # ── Step 2: Run STT + NLP pipeline (CPU-bound → thread pool) ─────────
        t_stt_start = _time.perf_counter()
        result = await asyncio.to_thread(
            pipeline.process_audio,
            tmp.name,
            session_id=session_id,
            language_hint=language or None,
            restaurant_id=restaurant_id,
        )
        t_stt_end = _time.perf_counter()
        stt_nlp_ms = round((t_stt_end - t_stt_start) * 1000)
        logger.info("⏱ STT+NLP pipeline: %dms (intent=%s, items=%d)",
                     stt_nlp_ms, result.get("intent"), len(result.get("items", [])))

        # ── Step 3: Send transcript + full pipeline result immediately ────────
        await websocket.send_json({
            "type": "final_transcript",
            "text": result.get("transcript", ""),
            "is_final": True,
            "detected_language": result.get("detected_language", "en"),
            "confidence": result.get("transcription_confidence", 0.0),
        })

        # Inject timing into result for frontend visibility
        result["_timing"] = {"stt_nlp_ms": stt_nlp_ms}

        await websocket.send_json({
            "type": "pipeline_result",
            **result,
        })

        # ── Step 4: Stream TTS audio chunks in real-time ─────────────────────
        # Client begins playback on first chunk — no wait for full synthesis.
        if cfg.TTS_ENABLED:
            try:
                import base64 as _b64
                from modules.voice.tts_engine_indic import indic_engine
                from modules.voice.llm_response import llm_generator
                from modules.voice import tts_normalizer

                detected_lang = result.get("detected_language", "en")

                # 4a. Generate spoken text (LLM/template)
                t_resp_start = _time.perf_counter()
                spoken_text = await llm_generator.get_response_text(result, detected_lang)
                t_resp_end = _time.perf_counter()
                resp_ms = round((t_resp_end - t_resp_start) * 1000)
                logger.info("⏱ Response text generation: %dms", resp_ms)

                if not spoken_text:
                    raise ValueError("No spoken text generated")

                normalized_text = tts_normalizer.normalize(spoken_text, detected_lang, result)

                # 4b. Ensure engine is ready
                if not indic_engine._ready:
                    indic_engine.warmup()

                if indic_engine._ready:
                    # 4c. STREAM — yield each TTS chunk as edge-tts produces it
                    chunk_index = 0
                    t_tts_start = _time.perf_counter()

                    async for chunk_bytes, is_sentinel in indic_engine.synthesize_streaming(
                        normalized_text, detected_lang
                    ):
                        if is_sentinel:
                            t_tts_end = _time.perf_counter()
                            tts_ms = round((t_tts_end - t_tts_start) * 1000)
                            await websocket.send_json({
                                "type": "tts_chunk",
                                "audio_b64": "",
                                "spoken_text": spoken_text if chunk_index == 0 else None,
                                "language": detected_lang,
                                "is_last": True,
                                "chunk_index": chunk_index,
                            })
                            break

                        if not chunk_bytes:
                            continue

                        audio_b64 = _b64.b64encode(chunk_bytes).decode("utf-8")

                        await websocket.send_json({
                            "type": "tts_chunk",
                            "audio_b64": audio_b64,
                            "spoken_text": spoken_text if chunk_index == 0 else None,
                            "language": detected_lang,
                            "is_last": False,
                            "chunk_index": chunk_index,
                        })
                        chunk_index += 1

                    t_tts_end = _time.perf_counter()
                    tts_ms = round((t_tts_end - t_tts_start) * 1000)
                    total_ms = stt_nlp_ms + resp_ms + tts_ms
                    logger.info(
                        "⏱ TTS streamed %d chunks in %dms | TOTAL: %dms (STT+NLP=%d, Response=%d, TTS=%d)",
                        chunk_index, tts_ms, total_ms, stt_nlp_ms, resp_ms, tts_ms,
                    )
                else:
                    # Engine not ready — send text only, client uses browser TTS
                    await websocket.send_json({
                        "type": "tts_chunk",
                        "audio_b64": None,
                        "spoken_text": spoken_text,
                        "language": detected_lang,
                        "is_last": True,
                    })

            except Exception as e:
                logger.warning("WebSocket TTS streaming failed: %s", e)
                # CRITICAL: Always send an is_last=True sentinel so the frontend
                # doesn't hang waiting for more chunks. Include the spoken text
                # so the client can fall back to browser TTS.
                try:
                    await websocket.send_json({
                        "type": "tts_chunk",
                        "audio_b64": None,
                        "spoken_text": spoken_text if 'spoken_text' in dir() else None,
                        "language": detected_lang if 'detected_lang' in dir() else "en",
                        "is_last": True,
                        "chunk_index": 0,
                    })
                except Exception:
                    pass  # WebSocket already closed

    except Exception as e:
        logger.exception("WebSocket audio processing failed")
        await websocket.send_json({
            "type": "error",
            "detail": f"Processing failed: {e}",
        })
    finally:
        Path(tmp.name).unlink(missing_ok=True)

