from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.templating import Jinja2Templates

from . import services
from .db import get_session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.filters["age"] = services.format_age
templates.env.filters["dayshort"] = lambda d: d.strftime("%-d %b")


def _list_context(error: str | None = None) -> dict:
    with get_session() as session:
        items = services.list_active(session)
    return {"items": items, "error": error}


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _list_context())


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


def _list_fragment(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "_list.html", _list_context(error))


@router.post("/items")
def create_item(request: Request, name: str = Form(...), portions: int = Form(...)):
    try:
        with get_session() as session:
            services.add_item(session, name, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, error=str(exc))
    return _list_fragment(request)


@router.post("/items/{item_id}/eat")
def eat_item(request: Request, item_id: int, portions: int = Form(...)):
    try:
        with get_session() as session:
            services.eat(session, item_id, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, error=str(exc))
    return _list_fragment(request)


@router.post("/items/{item_id}/add")
def add_to_item(request: Request, item_id: int, portions: int = Form(...)):
    try:
        with get_session() as session:
            services.add_batch(session, item_id, portions)
    except services.ValidationError as exc:
        return _list_fragment(request, error=str(exc))
    return _list_fragment(request)


@router.post("/items/{item_id}/discard")
def discard_item(request: Request, item_id: int):
    try:
        with get_session() as session:
            services.discard(session, item_id)
    except services.ValidationError as exc:
        return _list_fragment(request, error=str(exc))
    return _list_fragment(request)
