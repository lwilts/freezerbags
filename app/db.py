"""Database engine/session setup.

SQLite file lives at ${DATA_DIR}/freezerbags.db (DATA_DIR defaults to /data,
which is where the container mounts its persistent volume). WAL mode is
enabled so the single uvicorn worker can read/write without lock contention
on concurrent requests from two people's phones at once.
"""
from __future__ import annotations

import os
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "freezerbags.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    # Imported here (not at module top) so models are registered on Base
    # before create_all runs, without creating an import cycle.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
