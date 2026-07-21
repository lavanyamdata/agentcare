"""
session.py — Database engine and session management.
Creates the database connection and provides get_db() 
for all service files to use.
"""

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.config import DATABASE_URL
from app.database.models import Base

logger = logging.getLogger("agentcare.db")

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

# Enable SQLite performance settings
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready.")


@contextmanager
def get_db() -> Session:
    """
    Provides a database session.
    Always closes the session even if an error occurs.
    
    Usage:
        with get_db() as db:
            users = db.query(User).all()
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()