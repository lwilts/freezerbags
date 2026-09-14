from __future__ import annotations

import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routes import router

APP_DIR = Path(__file__).resolve().parent

# The base image's mimetypes database doesn't know .woff2, so StaticFiles
# would otherwise serve our vendored fonts as text/plain.
mimetypes.add_type("font/woff2", ".woff2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FreezerBags", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.include_router(router)
