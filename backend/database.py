"""
database.py - SQLAlchemy Engine & Session
=========================================
Connects to Supabase PostgreSQL using DATABASE_URL from .env.
Optimized for remote DB: persistent connections, statement timeout.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("petpooja.database")

# Load .env - try backend dir first, then project root.
_backend_dir = Path(__file__).parent
_project_root = _backend_dir.parent
load_dotenv(_backend_dir / ".env")
load_dotenv(_project_root / ".env")

_raw_database_url = os.getenv("DATABASE_URL", "").strip()

if not _raw_database_url:
    raise RuntimeError(
        "DATABASE_URL is not set in .env — cannot connect to Supabase. "
        "Please add your Supabase connection string to backend/.env"
    )


def _normalize_database_url(raw_url: str) -> str:
    """Normalize Postgres URL variants."""
    normalized = raw_url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized[len("postgres://"):]
    return normalized


DATABASE_URL = _normalize_database_url(_raw_database_url)
_safe_url = make_url(DATABASE_URL).render_as_string(hide_password=True)
logger.info("Connecting to Supabase PostgreSQL: %s", _safe_url)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # More persistent connections to avoid re-establishment
    max_overflow=5,
    pool_pre_ping=True,    # Drop stale connections before use
    pool_recycle=600,      # Recycle connections every 10 min
    pool_timeout=30,
    echo=False,
    # Set a generous statement timeout to avoid Supabase free-tier query cancellation
    connect_args={
        "options": "-c statement_timeout=60000",  # 60 seconds
    },
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency - yields a DB session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
