"""Hidden restore endpoint.

Not linked from any template -- protected by a required shared-secret
token rather than relying on the URL being undocumented, since this
overwrites the live database and the app itself has no login. Only
restore.sh (which fetches the token live from the cluster) is meant to
ever call this.
"""
from __future__ import annotations

import os
import secrets
from datetime import date

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import backup

router = APIRouter()

# Required, no default: fail fast at startup rather than silently running
# with an unprotected restore endpoint.
RESTORE_TOKEN = os.environ["RESTORE_TOKEN"]


class RestoreRequest(BaseModel):
    date: date


def _check_token(x_restore_token: str | None) -> None:
    if not x_restore_token or not secrets.compare_digest(x_restore_token, RESTORE_TOKEN):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/internal/restore")
def restore(payload: RestoreRequest, x_restore_token: str | None = Header(default=None)):
    _check_token(x_restore_token)
    try:
        backup.restore_backup(payload.date)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"No backup for {payload.date.isoformat()}",
                "available": [d.isoformat() for d in backup.list_backup_dates()],
            },
        )
    return {"status": "restored", "date": payload.date.isoformat()}
