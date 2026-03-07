"""
database.py — SQLAlchemy Engine & Session (Supabase PostgreSQL)
=================================================================
Connects to Supabase-hosted PostgreSQL via connection string in .env.
Falls back to local SQLite when DATABASE_URL is not set, or when USE_SQLITE=true.

If you see "could not translate host name ... to address: Name or service not known",
that is a DNS/network issue (no internet, firewall, or DNS blocking Supabase).
Use SQLite instead: set USE_SQLITE=true in backend/.env or leave DATABASE_URL unset.

Supabase requires SSL; we set sslmode=require for postgres URLs when not using SQLite.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger("petpooja.database")

# Load .env — try backend dir first, then project root, then cwd (for any start dir)
_backend_dir = Path(__file__).resolve().parent
_project_root = _backend_dir.parent
_cwd = Path.cwd()
load_dotenv(_backend_dir / ".env")
load_dotenv(_project_root / ".env")
if _cwd != _backend_dir:
    load_dotenv(_cwd / ".env")
    load_dotenv(_cwd / "backend" / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
_use_sqlite_raw = (os.getenv("USE_SQLITE") or "").strip().lower()
USE_SQLITE = _use_sqlite_raw in ("1", "true", "yes")


def _sqlite_engine():
    """Build SQLite engine and return (engine, path)."""
    path = Path(__file__).parent / "petpooja.db"
    url = f"sqlite:///{path}"
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    return eng, path


if USE_SQLITE or not DATABASE_URL:
    engine, _sqlite_path = _sqlite_engine()
    DATABASE_URL = str(engine.url)
    logger.warning(
        "Using local SQLite at %s. (USE_SQLITE=true or DATABASE_URL not set)",
        _sqlite_path,
    )
else:
    is_postgres = DATABASE_URL.strip().lower().startswith(("postgresql://", "postgres://"))
    connect_args = {}
    if is_postgres:
        connect_args["sslmode"] = "require"
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=60,
        connect_args=connect_args if connect_args else {},
        echo=False,
    )
    logger.info("Connected to PostgreSQL database (SSL enabled)")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
