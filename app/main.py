from __future__ import annotations

import asyncio
import datetime as dt
import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import backup
from .db import init_db
from .internal_routes import router as internal_router
from .routes import router
from .services import LONDON

APP_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

# The base image's mimetypes database doesn't know .woff2, so StaticFiles
# would otherwise serve our vendored fonts as text/plain.
mimetypes.add_type("font/woff2", ".woff2")


async def _daily_backup_loop() -> None:
    while True:
        now = dt.datetime.now(LONDON)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += dt.timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            backup.create_backup()
        except Exception:
            logger.exception("Daily backup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        # So a fresh install has a backup from day one, not just from 3am.
        backup.create_backup()
    except Exception:
        logger.exception("Startup backup failed")
    task = asyncio.create_task(_daily_backup_loop())
    yield
    task.cancel()


app = FastAPI(title="FreezerBags", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.include_router(router)
app.include_router(internal_router)
