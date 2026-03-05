"""
Petpooja AI Copilot — FastAPI Application Entry Point
======================================================
No external APIs — everything runs locally.
SQLite database, faster-whisper STT, rule-based NLP.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from api.routes_revenue import router as revenue_router
from api.routes_voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    print("🚀 Petpooja AI Copilot — Server ready")
    print("📊 Revenue engine loaded")
    print("🎙️ Voice pipeline ready (faster-whisper)")
    yield
    print("Server shutting down...")


app = FastAPI(
    title="Petpooja AI Copilot",
    description="Restaurant Revenue Intelligence & Voice Ordering — fully offline, no external APIs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route registration ──
app.include_router(revenue_router, prefix="/api/revenue", tags=["Revenue"])
app.include_router(voice_router, prefix="/api/voice", tags=["Voice"])


@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "petpooja-ai-copilot", "mode": "offline"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
