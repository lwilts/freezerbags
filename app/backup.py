"""Daily SQLite snapshots + restore.

Uses plain sqlite3 against the db file directly rather than going through
SQLAlchemy -- this is a file-level operation (VACUUM INTO a new file, or
overwrite the live file from an old one), not something the ORM needs to
be involved in.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from . import db
from .services import today_london

BACKUP_DIR = db.DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

RETENTION_DAYS = 30

_NAME_RE = re.compile(r"^freezerbags-(\d{4}-\d{2}-\d{2})\.db$")


def _path_for(target_date: date) -> Path:
    return BACKUP_DIR / f"freezerbags-{target_date.isoformat()}.db"


def list_backup_dates() -> list[date]:
    dates = []
    for f in BACKUP_DIR.glob("freezerbags-*.db"):
        m = _NAME_RE.match(f.name)
        if m:
            dates.append(date.fromisoformat(m.group(1)))
    return sorted(dates)


def create_backup(today: date | None = None) -> Path:
    """Snapshot the live db via VACUUM INTO -- safe to run while the app is
    serving requests, and produces one consistent, compacted file. Deletes
    an existing same-day backup first since VACUUM INTO refuses to write
    over an existing file, so re-running this (e.g. on every container
    startup) is a harmless overwrite rather than an error.
    """
    today = today or today_london()
    target = _path_for(today)
    if target.exists():
        target.unlink()

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(f"VACUUM INTO '{target}'")
    finally:
        conn.close()

    prune_old_backups(today=today)
    return target


def prune_old_backups(today: date | None = None) -> list[Path]:
    """Delete backups older than RETENTION_DAYS. Returns what was removed."""
    today = today or today_london()
    cutoff = today - timedelta(days=RETENTION_DAYS)
    removed = []
    for f in BACKUP_DIR.glob("freezerbags-*.db"):
        m = _NAME_RE.match(f.name)
        if m and date.fromisoformat(m.group(1)) < cutoff:
            f.unlink()
            removed.append(f)
    return removed


def restore_backup(target_date: date) -> None:
    """Overwrite the live db with the snapshot from `target_date`.

    Disposes the SQLAlchemy engine's connection pool first so nothing has
    the old file open, removes the live db's WAL/SHM sidecars (they refer
    to the file we're about to replace and would otherwise leave stale
    pages), then copies the backup over the live path. The engine
    reconnects lazily on the next query.
    """
    source = _path_for(target_date)
    if not source.exists():
        raise FileNotFoundError(f"No backup for {target_date.isoformat()}")

    db.engine.dispose()

    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db.DB_PATH) + suffix)
        if sidecar.exists():
            sidecar.unlink()

    shutil.copyfile(source, db.DB_PATH)
