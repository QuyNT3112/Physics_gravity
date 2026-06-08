"""
database.py – SQLAlchemy engine, session factory, and DB initialization.

Supports both SQLite (development) and PostgreSQL (production).
Switch between them by setting the DATABASE_URL environment variable:

  SQLite (default):    sqlite:///physics_sim.db
  PostgreSQL:          postgresql://user:pass@localhost:5432/physics_db
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load .env file if present
load_dotenv()

# ── Database URL ───────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///physics_sim.db")

# ── Engine Configuration ────────────────────────────────────────────────────────
_engine_kwargs: dict = {}

if DATABASE_URL.startswith("sqlite"):
    # SQLite: enable WAL mode and foreign keys
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "echo": os.getenv("FLASK_DEBUG", "false").lower() == "true",
    }
else:
    # PostgreSQL: connection pooling config
    _engine_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "echo": os.getenv("FLASK_DEBUG", "false").lower() == "true",
    }

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Enable SQLite WAL mode and foreign key enforcement
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ── Session Factory ─────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ── Base Class for ORM Models ───────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Session Context Manager ─────────────────────────────────────────────────────
@contextmanager
def get_db_session():
    """
    Context manager that provides a transactional database session.

    Usage:
        with get_db_session() as db:
            db.add(some_model_instance)
            db.commit()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """
    Generator for Flask dependency injection pattern.

    Usage in Flask routes:
        db = next(get_db())
        try:
            ...
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Database Initialization ─────────────────────────────────────────────────────
def init_db():
    """
    Create all tables defined in models.py.
    Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).
    """
    from models import Base as ModelsBase  # noqa: F401 – import to register models
    ModelsBase.metadata.create_all(bind=engine)
    print(f"[DB] Database initialized at: {DATABASE_URL}")
    print(f"[DB] Engine: {engine.dialect.name}")


def get_db_info() -> dict:
    """Return basic database connection info for health check."""
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.execute(text("SELECT sqlite_version()")).fetchone()
            version = f"SQLite {result[0]}"
        else:
            result = conn.execute(text("SELECT version()")).fetchone()
            version = result[0]

    return {
        "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "dialect": engine.dialect.name,
        "version": version,
        "pool_status": {
            "size": getattr(engine.pool, "size", lambda: "N/A")(),
            "checked_in": getattr(engine.pool, "checkedin", lambda: "N/A")(),
            "checked_out": getattr(engine.pool, "checkedout", lambda: "N/A")(),
        }
    }
